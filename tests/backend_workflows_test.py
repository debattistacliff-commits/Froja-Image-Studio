import unittest

import backend


class WorkflowBuilderTests(unittest.TestCase):
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
        self.assertEqual(workflow["1"]["class_type"], "UNETLoader")
        self.assertEqual(workflow["9"]["inputs"]["steps"], 4)
        self.assertEqual(workflow["9"]["inputs"]["cfg"], 1.0)
        self.assertEqual(workflow["9"]["inputs"]["sampler_name"], "res_multistep")

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
