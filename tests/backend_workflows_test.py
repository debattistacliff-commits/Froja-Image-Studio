import unittest
import tempfile
import urllib.parse
from pathlib import Path

import backend


class WorkflowBuilderTests(unittest.TestCase):
    def test_numbered_forge_gallery_image_can_be_used_as_preview(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "bronze_archer.safetensors"
            model.touch()
            preview = Path(folder) / "bronze_archer_0.png"
            preview.write_bytes(b"preview")
            self.assertEqual(urllib.parse.unquote(backend.find_preview(model)), str(preview))

    def test_flux2_large_files_are_not_classified_as_compact(self):
        self.assertEqual(backend.architecture("flux-2-klein-4b-Q4_0.gguf"), "Flux2-Klein")
        self.assertEqual(backend.architecture("flux-2-klein-4b.safetensors"), "Flux2-Large")
        self.assertEqual(backend.architecture("flux-2-klein-9b-fp8.safetensors"), "Flux2-Large")
        self.assertEqual(backend.architecture("flux2KleinAIO_flux24BDistilledAIO.safetensors"), "Flux2-Large")

    def test_gpu_memory_handoff_is_available_for_isolated_engines(self):
        self.assertTrue(callable(backend.release_engine_memory))

    def test_standard_checkpoint_workflow_keeps_user_settings(self):
        workflow = backend.build_workflow({
            "checkpoint": "example.safetensors",
            "architecture": "SDXL",
            "prompt": "a bronze observatory",
            "negative_prompt": "blurred",
            "width": 1024,
            "height": 768,
            "steps": 30,
            "cfg": 6.5,
            "seed": 42,
            "sampler": "dpmpp_2m",
            "scheduler": "karras",
        })
        self.assertEqual(workflow["1"]["inputs"]["ckpt_name"], "example.safetensors")
        self.assertEqual(workflow["4"]["inputs"]["width"], 1024)
        self.assertEqual(workflow["5"]["inputs"]["seed"], 42)
        self.assertEqual(workflow["5"]["inputs"]["steps"], 30)
        self.assertEqual(workflow["5"]["inputs"]["cfg"], 6.5)

    def test_z_image_uses_turbo_pipeline(self):
        workflow = backend.build_workflow({
            "checkpoint": "zImageBase_base.safetensors",
            "architecture": "Z-Image",
            "prompt": "monumental hall",
            "width": 1024,
            "height": 1024,
            "seed": 7,
        })
        self.assertEqual(workflow["1"]["class_type"], "CheckpointLoaderSimple")
        self.assertEqual(workflow["1"]["inputs"]["ckpt_name"], "zImageBase_base.safetensors")
        self.assertEqual(workflow["9"]["inputs"]["steps"], 4)
        self.assertEqual(workflow["9"]["inputs"]["cfg"], 1.0)
        self.assertEqual(workflow["9"]["inputs"]["sampler_name"], "res_multistep")

    def test_darkbeast_checkpoint_uses_krea_components(self):
        workflow = backend.build_workflow({
            "checkpoint": "darkBeast30BF16INT8_darkBeast330.safetensors",
            "architecture": "Krea-2",
            "prompt": "a bronze statue in a gallery",
        })
        self.assertEqual(workflow["1"]["class_type"], "CheckpointLoaderSimple")
        self.assertEqual(workflow["1"]["inputs"]["ckpt_name"], "darkBeast30BF16INT8_darkBeast330.safetensors")
        self.assertEqual(workflow["2"]["inputs"]["clip_name"], "qwen3vl_4b_fp8_scaled.safetensors")
        self.assertEqual(workflow["6"]["inputs"]["vae_name"], "qwen_image_vae.safetensors")

    def test_flux_checkpoint_uses_flux_pipeline(self):
        workflow = backend.build_workflow({
            "checkpoint": "flux1-dev.safetensors",
            "architecture": "Flux",
            "prompt": "a polished bronze robot",
            "negative_prompt": "blurry",
            "steps": 8,
            "width": 1024,
            "height": 1024,
        })
        self.assertEqual(workflow["2"]["class_type"], "DualCLIPLoader")
        self.assertEqual(workflow["2"]["inputs"]["type"], "flux")
        self.assertEqual(workflow["4"]["class_type"], "FluxGuidance")
        self.assertEqual(workflow["6"]["class_type"], "EmptySD3LatentImage")
        self.assertEqual(workflow["7"]["inputs"]["vae_name"], "ae.safetensors")
        self.assertEqual(workflow["20"]["class_type"], "ModelSamplingFlux")

    def test_flux2_klein_uses_compact_native_pipeline(self):
        workflow = backend.build_workflow({
            "checkpoint": "flux-2-klein-4b-Q4_0.gguf",
            "architecture": "Flux2-Klein",
            "prompt": "a bronze observatory at sunrise",
            "width": 512,
            "height": 512,
            "seed": 42,
        })
        self.assertEqual(workflow["1"]["class_type"], "UnetLoaderGGUF")
        self.assertEqual(workflow["2"]["inputs"]["clip_name"], "qwen_3_4b_fp4_flux2.safetensors")
        self.assertEqual(workflow["2"]["inputs"]["type"], "flux2")
        self.assertEqual(workflow["5"]["class_type"], "EmptyFlux2LatentImage")
        self.assertEqual(workflow["9"]["inputs"]["steps"], 4)
        self.assertEqual(workflow["10"]["inputs"]["cfg"], 1.0)
        self.assertEqual(workflow["11"]["class_type"], "SamplerCustomAdvanced")

    def test_mage_flow_uses_compact_int8_pipeline(self):
        workflow = backend.build_workflow({
            "checkpoint": "mage_flow_turbo_int8_convrot.safetensors",
            "architecture": "Mage-Flow",
            "prompt": "a luminous glass sculpture",
            "negative_prompt": "blurry",
            "width": 512,
            "height": 512,
            "seed": 42,
        })
        self.assertEqual(workflow["1"]["class_type"], "UNETLoader")
        self.assertEqual(workflow["2"]["inputs"]["clip_name"], "qwen3vl_4b_fp8_scaled.safetensors")
        self.assertEqual(workflow["2"]["inputs"]["type"], "mage")
        self.assertEqual(workflow["3"]["inputs"]["vae_name"], "mage_flow_vae_bf16.safetensors")
        self.assertEqual(workflow["4"]["class_type"], "TextEncodeMageFlowEdit")
        self.assertEqual(workflow["5"]["inputs"]["steps"], 4)
        self.assertEqual(workflow["5"]["inputs"]["cfg"], 1.0)

    def test_krea_2_uses_distilled_pipeline(self):
        workflow = backend.build_workflow({
            "checkpoint": "krea2-turbo.gguf",
            "architecture": "Krea-2",
            "prompt": "fine-art portrait",
            "width": 1024,
            "height": 1024,
            "seed": 9,
        })
        self.assertEqual(workflow["1"]["class_type"], "UnetLoaderGGUF")
        self.assertEqual(workflow["7"]["inputs"]["steps"], 8)
        self.assertEqual(workflow["7"]["inputs"]["cfg"], 1.0)
        self.assertEqual(workflow["7"]["inputs"]["sampler_name"], "er_sde")

    def test_dimensions_and_sampling_are_safely_clamped(self):
        workflow = backend.build_workflow({
            "checkpoint": "example.safetensors",
            "prompt": "test",
            "width": 99999,
            "height": 1,
            "steps": 999,
            "cfg": 999,
            "seed": 1,
        })
        self.assertEqual(workflow["4"]["inputs"]["width"], 2048)
        self.assertEqual(workflow["4"]["inputs"]["height"], 256)
        self.assertEqual(workflow["5"]["inputs"]["steps"], 100)
        self.assertEqual(workflow["5"]["inputs"]["cfg"], 30)


if __name__ == "__main__":
    unittest.main()
