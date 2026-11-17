import io
import json
import unittest
import zipfile
from unittest.mock import patch

import backend
from workflow_builder import api_to_ui, make_pack, validate_api


def info(required, outputs=()):
    return {"input": {"required": required}, "output": list(outputs), "output_name": list(outputs)}


OBJECT_INFO = {
    "CheckpointLoaderSimple": info({"ckpt_name": [["folder/model.safetensors"]]}, ["MODEL", "CLIP", "VAE"]),
    "CLIPTextEncode": info({"text": ["STRING", {"default": ""}], "clip": ["CLIP"]}, ["CONDITIONING"]),
    "EmptyLatentImage": info({"width": ["INT"], "height": ["INT"], "batch_size": ["INT"]}, ["LATENT"]),
    "KSampler": info({"model": ["MODEL"], "seed": ["INT", {"control_after_generate": True}], "steps": ["INT"],
                      "cfg": ["FLOAT"], "sampler_name": [["euler"]], "scheduler": [["normal"]],
                      "positive": ["CONDITIONING"], "negative": ["CONDITIONING"], "latent_image": ["LATENT"], "denoise": ["FLOAT"]}, ["LATENT"]),
    "VAEDecode": info({"samples": ["LATENT"], "vae": ["VAE"]}, ["IMAGE"]),
    "SaveImage": info({"images": ["IMAGE"], "filename_prefix": ["STRING"]}),
}


def graph():
    return backend.build_workflow({"checkpoint": "folder/model.safetensors", "architecture": "SDXL", "prompt": "a tower", "seed": 42,
                                   "width": 512, "height": 512, "steps": 20, "cfg": 7, "sampler": "euler", "scheduler": "normal"})


class WorkflowBuilderTests(unittest.TestCase):
    def test_slots_links_and_layout(self):
        api = graph()
        self.assertEqual(validate_api(api, OBJECT_INFO), [])
        ui = api_to_ui(api, OBJECT_INFO)
        nodes = {n["id"]: n for n in ui["nodes"]}
        for link_id, source, output, target, slot, typ in ui["links"]:
            self.assertEqual(nodes[target]["inputs"][slot]["link"], link_id)
            self.assertIn(link_id, nodes[source]["outputs"][output]["links"])
            self.assertEqual(nodes[source]["outputs"][output]["slot_index"], output)
            self.assertEqual(nodes[source]["outputs"][output]["type"], typ)
            self.assertLess(nodes[source]["order"], nodes[target]["order"])
            self.assertLess(nodes[source]["pos"][0], nodes[target]["pos"][0])
        self.assertEqual(ui["version"], 0.4)

    def test_widget_order_and_converted_widget(self):
        api = graph()
        ui = api_to_ui(api, OBJECT_INFO)
        sampler = next(n for n in ui["nodes"] if n["type"] == "KSampler")
        self.assertEqual(sampler["widgets_values"], [42, "fixed", 20, 7.0, "euler", "normal", 1.0])
        api["4"]["inputs"]["width"] = ["4source", 0]
        api["4source"] = {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}}
        ui = api_to_ui(api, OBJECT_INFO)
        latent = next(n for n in ui["nodes"] if n["id"] == 4)
        self.assertEqual(latent["inputs"][0]["widget"], {"name": "width"})
        self.assertIsInstance(latent["inputs"][0]["link"], int)

    def test_validation(self):
        api = graph()
        api["5"]["inputs"]["model"] = ["missing", 0]
        api["6"]["inputs"]["vae"] = ["1", 9]
        api["unknown"] = {"class_type": "UnknownNode", "inputs": {}}
        del api["4"]["inputs"]["width"]
        problems = " ".join(validate_api(api, OBJECT_INFO))
        for text in ["missing node", "out of range", "UnknownNode", "missing required input width"]:
            self.assertIn(text, problems)
        with self.assertRaisesRegex(ValueError, "UnknownNode"):
            api_to_ui(api, OBJECT_INFO)

    def test_pack_portability(self):
        api = graph()
        api["1"]["inputs"]["ckpt_name"] = r"C:\Users\Alice\ComfyUI\models\checkpoints\folder\model.safetensors"
        pack = make_pack("Example", api, api_to_ui(api, OBJECT_INFO),
                         {"description": r"Use G:\Users\Alice\private\image.png and /home/alice/photo.png"}, b"png", {r"G:\Users\Alice\input.png": b"input"},
                         [{"kind": "checkpoint", "relative": api["1"]["inputs"]["ckpt_name"], "size": 2_000_000_000}])
        with zipfile.ZipFile(io.BytesIO(pack)) as archive:
            self.assertEqual(set(archive.namelist()), {"workflow_ui.json", "workflow_api.json", "plan.json", "sample.png", "inputs/input.png", "models.txt", "README.md"})
            for name in archive.namelist():
                data = archive.read(name).decode()
                for forbidden in ["C:\\", "G:\\", "Users", "/home/alice"]:
                    self.assertNotIn(forbidden, data)
            exported = json.loads(archive.read("workflow_api.json"))
            self.assertEqual(exported["1"]["inputs"]["ckpt_name"], "folder/model.safetensors")
            self.assertIn("2.000 GB", archive.read("models.txt").decode())

    def test_invalid_ids(self):
        for identifier in ["../escape", "a/b", "C:\\temp", "", None]:
            with self.assertRaises(ValueError):
                backend.workflow_builder_folder(identifier)

    def test_run_uses_main_engine_memory_handoff(self):
        from unittest.mock import Mock
        folder = Mock()
        folder.__truediv__ = Mock(return_value=Mock(read_text=Mock(return_value=json.dumps(graph()))))
        handler = Mock()
        with patch.object(backend, "read_json_body", return_value={"id": "saved"}), \
             patch.object(backend, "workflow_builder_folder", return_value=folder), \
             patch.object(backend, "comfy_ready", return_value=True), \
             patch.object(backend, "engine_has_queued_work", return_value=False), \
             patch.object(backend, "release_engine_memory") as release, \
             patch.object(backend, "comfy_request", return_value={"prompt_id": "queued"}) as request, \
             patch.object(backend, "json_response") as response:
            backend.workflow_builder_post(handler, "run")
            release.assert_called_once_with("extension", "joyai", "sensenova", "ollama")
            self.assertEqual(request.call_args.args[0], "/prompt")
            response.assert_called_once_with(handler, {"prompt_id": "queued"})

    def test_object_info_cache(self):
        with patch.dict(backend._WORKFLOW_INFO, {"at": 0, "url": "", "data": {}}), patch.object(backend, "comfy_request", return_value=OBJECT_INFO) as request:
            self.assertEqual(backend.workflow_builder_info(), OBJECT_INFO)
            self.assertEqual(backend.workflow_builder_info(), OBJECT_INFO)
            request.assert_called_once()

    def test_paths_with_spaces_are_fully_removed(self):
        from workflow_builder import _portable
        bs = chr(92)
        value = "C:/Users/Alice Smith/ComfyUI/models/checkpoints/my model.safetensors"
        self.assertEqual(_portable(value), "my model.safetensors")
        self.assertEqual(_portable("D:" + bs + "My Files" + bs + "ref photo.png"), "ref photo.png")
        self.assertEqual(_portable("Users walking in a park"), "Users walking in a park")
        self.assertEqual(_portable("folder" + bs + "x.safetensors"), "folder" + bs + "x.safetensors")

if __name__ == "__main__":
    unittest.main()
