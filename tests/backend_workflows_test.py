import json
import unittest
import tempfile
import urllib.parse
from pathlib import Path
from unittest.mock import patch

import backend


class WorkflowBuilderTests(unittest.TestCase):
    def test_ollama_reasoning_response_can_supply_vision_text(self):
        result = {"message": {"content": "", "thinking": "<think>A red bicycle beside a brick wall.</think>"}}
        self.assertEqual(backend.ollama_message_text(result), "A red bicycle beside a brick wall.")

    def test_truncated_safetensor_is_rejected_before_model_scan(self):
        header = {"weight": {"dtype": "F32", "shape": [4], "data_offsets": [0, 16]}}
        encoded = json.dumps(header).encode("utf-8")
        with tempfile.TemporaryDirectory() as folder:
            complete = Path(folder) / "complete.safetensors"
            complete.write_bytes(len(encoded).to_bytes(8, "little") + encoded + bytes(16))
            truncated = Path(folder) / "truncated.safetensors"
            truncated.write_bytes(len(encoded).to_bytes(8, "little") + encoded + bytes(8))
            self.assertTrue(backend.safetensor_is_complete(complete))
            self.assertFalse(backend.safetensor_is_complete(truncated))

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

    def test_auxiliary_models_are_not_presented_as_checkpoints(self):
        self.assertTrue(backend.model_is_auxiliary(Path("controlnetxlCNXL_hetanekoCanny_410511.safetensors")))
        self.assertTrue(backend.model_is_auxiliary(Path("ip_adapter_plus.safetensors")))
        self.assertFalse(backend.model_is_auxiliary(Path("realisticVisionXL_v60.safetensors")))
    def test_gpu_memory_handoff_is_available_for_isolated_engines(self):
        self.assertTrue(callable(backend.release_engine_memory))

    def test_camera_view_workflow_uses_qwen_edit_with_four_step_sampling(self):
        workflow = backend.build_camera_view_workflow({"instruction": "rotate_right_45", "seed": 42}, "FrojaSpin/photo.png")
        self.assertEqual([node["class_type"] for node in workflow.values()], [
            "LoadImage", "ImageScaleToTotalPixels", "UNETLoader", "LoraLoaderModelOnly",
            "LoraLoaderModelOnly", "ModelSamplingAuraFlow", "CFGNorm", "CLIPLoader", "VAELoader",
            "TextEncodeQwenImageEditPlus", "ConditioningZeroOut", "VAEEncode", "KSampler", "VAEDecode",
            "GetImageSize", "ImageScale", "SaveImage",
        ])
        self.assertEqual(workflow["1"]["inputs"]["image"], "FrojaSpin/photo.png")
        self.assertEqual(workflow["3"]["inputs"]["unet_name"], "qwen_image_edit_2509_fp8_e4m3fn.safetensors")
        self.assertEqual(workflow["4"]["inputs"]["lora_name"], "Qwen-Edit-2509-Multiple-angles.safetensors")
        self.assertEqual(workflow["5"]["inputs"]["lora_name"], "Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors")
        self.assertEqual(workflow["5"]["inputs"]["model"], ["4", 0])
        self.assertEqual(workflow["10"]["inputs"]["image1"], ["1", 0])
        self.assertNotIn("image2", workflow["10"]["inputs"])
        self.assertEqual(workflow["16"]["inputs"]["image"], ["1", 0])
        self.assertEqual(workflow["17"]["inputs"]["width"], ["16", 0])
        self.assertEqual(workflow["17"]["inputs"]["height"], ["16", 1])
        self.assertEqual(workflow["17"]["inputs"]["crop"], "disabled")
        self.assertEqual(workflow["15"]["inputs"]["images"], ["17", 0])
        sampler = workflow["13"]["inputs"]
        self.assertEqual((sampler["steps"], sampler["cfg"], sampler["seed"]), (4, 1.0, 42))

    def test_camera_view_workflow_maps_supported_instructions(self):
        for instruction, prompt in {
            "rotate_left_45": "将镜头向左旋转45度",
            "rotate_right_45": "将镜头向右旋转45度",
            "rotate_left_90": "将镜头向左旋转90度",
            "rotate_right_90": "将镜头向右旋转90度",
            "top": "将镜头转为俯视",
            "low": "将镜头转为仰视",
            "closeup": "将镜头转为特写镜头",
            "wide": "将镜头转为广角镜头",
        }.items():
            with self.subTest(instruction=instruction):
                workflow = backend.build_camera_view_workflow({"instruction": instruction}, "photo.png")
                actual = workflow["10"]["inputs"]["prompt"]
                if instruction.startswith("rotate_"):
                    self.assertIn(prompt, actual)
                    self.assertIn("Keep exactly the same person from image 1", actual)
                else:
                    self.assertEqual(actual, prompt)
                self.assertIn(workflow["13"]["inputs"]["seed"], range(2**32))

    def test_camera_spin_uses_side_guides_for_rear_angles(self):
        for instruction, target, rotation in (
            ("rear_right", "135 degrees to the right of image 1", "将镜头向右旋转45度"),
            ("back", "straight back view", "将镜头向右旋转90度"),
            ("rear_left", "135 degrees to the left of image 1", "将镜头向左旋转45度"),
        ):
            with self.subTest(instruction=instruction):
                payload = {"instruction": instruction, "seed": 42}
                workflow = backend.build_camera_view_workflow(payload, "original.png", "profile.png")
                conditioning = workflow["10"]["inputs"]
                self.assertEqual(workflow["1"]["inputs"]["image"], "original.png")
                self.assertEqual(workflow["18"]["inputs"]["image"], "profile.png")
                self.assertEqual((conditioning["image1"], conditioning["image2"]), (["1", 0], ["18", 0]))
                self.assertIn(target, conditioning["prompt"])
                self.assertIn(f"From the camera position in image 2: {rotation}", conditioning["prompt"])
                self.assertEqual(workflow["13"]["inputs"]["seed"], 42)
                with self.assertRaises(ValueError):
                    backend.build_camera_view_workflow(payload, "original.png")

    def test_camera_view_workflow_rejects_unsupported_instructions(self):
        for instruction in ("rotate", "", None, []):
            with self.subTest(instruction=instruction), self.assertRaises(ValueError):
                backend.build_camera_view_workflow({"instruction": instruction}, "photo.png")

    def test_camera_position_maps_every_azimuth(self):
        expected = {
            0: "front view",
            45: "将镜头向右旋转45度",
            90: "将镜头向右旋转90度",
            135: "将镜头向右旋转135度",
            180: "将镜头向右旋转180度",
            225: "将镜头向左旋转135度",
            270: "将镜头向左旋转90度",
            315: "将镜头向左旋转45度",
        }
        for azimuth, command in expected.items():
            with self.subTest(azimuth=azimuth):
                prompt = backend.camera_position_prompt(azimuth, "eye", "medium")
                self.assertIn(command, prompt)
                self.assertIn("eye level, medium shot", prompt)
                self.assertIn("Keep the same background location", prompt)

    def test_camera_position_combines_elevation_and_distance(self):
        high = backend.camera_position_prompt(45, "high", "wide")
        self.assertIn("将镜头向右旋转45度。 将镜头转为俯视。 将镜头转为广角镜头", high)
        self.assertIn("high angle, looking down, wide shot", high)
        self.assertNotIn("Keep the subject about the same size", high)
        low = backend.camera_position_prompt(315, "low", "closeup")
        self.assertIn("将镜头向左旋转45度。 将镜头转为仰视。 将镜头转为特写镜头", low)
        self.assertIn("low angle, looking up, close-up", low)

    def test_camera_position_workflow_keeps_the_master_as_image_one(self):
        workflow = backend.build_camera_view_workflow({"azimuth": 180, "seed": 42}, "master.png", "profile.png")
        conditioning = workflow["10"]["inputs"]
        self.assertEqual(workflow["1"]["inputs"]["image"], "master.png")
        self.assertEqual((conditioning["image1"], conditioning["image2"]), (["1", 0], ["18", 0]))
        self.assertIn("From the camera position in image 2: 将镜头向右旋转90度", conditioning["prompt"])
        self.assertIn("straight back view", conditioning["prompt"])
        self.assertIn("face fully hidden", conditioning["prompt"])

    def test_camera_position_rejects_invalid_settings(self):
        valid = {"azimuth": 45, "elevation": "eye", "distance": "medium"}
        for field, values in (
            ("azimuth", (None, True, 45.0, "45", 1, -45, 360)),
            ("elevation", (None, [], 0, "eye-level", "top")),
            ("distance", (None, {}, "zoom", False)),
        ):
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    backend.build_camera_view_workflow({**valid, field: value}, "master.png")

    def test_inpaint_can_preserve_pixels_outside_the_mask(self):
        with patch.object(backend, "save_face_upload", side_effect=lambda _data, label: f"{label}.png"):
            payload = {"mode": "inpaint", "prompt": "a black hoodie"}
            standard = backend.build_image_tool_workflow(payload)
            preserved = backend.build_image_tool_workflow({**payload, "preserve_unmasked": True})

        self.assertEqual(standard["32"]["inputs"]["images"], ["31", 0])
        self.assertEqual(preserved["32"]["inputs"]["images"], ["33", 0])
        self.assertEqual(preserved["33"]["class_type"], "ImageCompositeMasked")
        composite = preserved["33"]["inputs"]
        self.assertEqual((composite["destination"], composite["source"], composite["mask"]),
                         (["10", 0], ["31", 0], ["11", 0]))

    def test_mask_from_text_workflow_routes_the_mask_and_clamps_settings(self):
        prompt = "the shirt · the blue sleeve"
        for options, expected in (
            ({}, (0.30, 0, False)),
            ({"threshold": -1, "grow": -4}, (0.05, 0, False)),
            ({"threshold": 2, "grow": 100, "invert": True}, (0.95, 64, True)),
        ):
            with self.subTest(options=options):
                workflow = backend.build_mask_from_text_workflow({"prompt": prompt, **options}, "FrojaFace/source.png")
                threshold, grow, invert = expected
                self.assertEqual([node["class_type"] for node in workflow.values()], [
                    "LoadImage", "SAM2Segment", "ThresholdMask",
                    *(["GrowMask"] if grow else []), "MaskToImage", "SaveImage",
                ])
                self.assertEqual(workflow["1"]["inputs"]["image"], "FrojaFace/source.png")
                segment = workflow["2"]["inputs"]
                self.assertEqual(segment["image"], ["1", 0])
                self.assertEqual(segment["prompt"], prompt)
                self.assertEqual((segment["threshold"], segment["mask_offset"], segment["invert_output"]), (threshold, 0, invert))
                self.assertEqual(workflow["3"]["inputs"], {"mask": ["2", 1], "value": 0.5})
                if grow:
                    self.assertEqual(workflow["4"]["inputs"], {"mask": ["3", 0], "expand": grow, "tapered_corners": True})
                self.assertEqual(workflow["5"]["inputs"]["mask"], ["4" if grow else "3", 0])
                self.assertEqual(workflow["6"]["inputs"], {"images": ["5", 0], "filename_prefix": "Froja/maskwords"})

    def test_private_video_defaults_to_disabled_in_public_config(self):
        self.assertTrue(callable(backend.wangp_status))
        self.assertIn("private", backend.wangp_status())

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
        self.assertEqual(workflow["1"]["inputs"]["unet_name"], "zImageBase_base.safetensors")
        self.assertEqual(workflow["4"]["class_type"], "CLIPLoader")
        self.assertEqual(workflow["5"]["inputs"]["clip"], ["4", 0])
        self.assertEqual(workflow["8"]["class_type"], "VAELoader")
        self.assertEqual(workflow["10"]["inputs"]["vae"], ["8", 0])
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

    def test_minimax_h3_image_is_detected_by_filename(self):
        self.assertEqual(backend.architecture("minimax_h3_image_pruned_int8_convrot.safetensors"), "MiniMax-H3-Image")
        # The MiniMax H3 video model must not be mistaken for the image model.
        self.assertNotEqual(backend.architecture("minimax_h3_fl2va_pruned_int8_convrot.safetensors"), "MiniMax-H3-Image")

    def test_minimax_h3_image_uses_official_t2i_pipeline(self):
        workflow = backend.build_workflow({
            "checkpoint": "minimax_h3_image_pruned_int8_convrot.safetensors",
            "architecture": "MiniMax-H3-Image",
            "prompt": "a plush fox above a summer meadow",
            "negative_prompt": "ignored",
            "width": 1024,
            "height": 768,
            "steps": 30,
            "cfg": 7,
            "seed": 42,
        })
        self.assertEqual(workflow["1"]["class_type"], "UNETLoader")
        self.assertEqual(workflow["2"]["inputs"]["type"], "minimax")
        self.assertEqual(workflow["3"]["inputs"]["vae_name"], "minimax_h3_image_vae_fp16.safetensors")
        conditioning = workflow["4"]["inputs"]
        self.assertEqual(workflow["4"]["class_type"], "MiniMaxH3ImageConditioning")
        self.assertEqual(conditioning["prompt"], "a plush fox above a summer meadow")
        # Small canvases are scaled up to ~2048x2048 of area, keeping 4:3 and multiples of 32.
        self.assertEqual(conditioning["width"] % 32, 0)
        self.assertEqual(conditioning["height"] % 32, 0)
        self.assertGreaterEqual(conditioning["width"] * conditioning["height"], int(2048 * 2048 * 0.95))
        self.assertAlmostEqual(conditioning["width"] / conditioning["height"], 4 / 3, delta=0.03)
        sampler = workflow["6"]["inputs"]
        self.assertEqual((sampler["steps"], sampler["cfg"], sampler["sampler_name"]), (6, 1.0, "euler"))
        self.assertEqual(sampler["latent_image"], ["4", 1])
        self.assertEqual(sampler["negative"], ["5", 0])

    def test_qwen_image_21_uses_official_int8_pipeline(self):
        workflow = backend.build_workflow({
            "checkpoint": "qwen_image_2.1_int8_convrot.safetensors",
            "architecture": "Qwen-Image-2.1",
            "prompt": "a glass lighthouse in a storm",
            "negative_prompt": "text",
            "width": 1024,
            "height": 1024,
            "steps": 25,
            "cfg": 7,
            "seed": 42,
        })
        self.assertEqual(workflow["1"]["class_type"], "UNETLoader")
        self.assertEqual(workflow["2"]["inputs"]["clip_name"], "qwen3vl_8b_int8_convrot.safetensors")
        self.assertEqual(workflow["2"]["inputs"]["type"], "qwen_image")
        self.assertEqual(workflow["3"]["class_type"], "TextEncodeQwenImage21")
        self.assertEqual(workflow["3"]["inputs"]["resolution"], 1024)
        self.assertEqual(workflow["5"]["inputs"]["vae_name"], "qwen_image_2.1_vae_bf16.safetensors")
        self.assertEqual(workflow["6"]["inputs"]["cfg"], 1.0)
        self.assertEqual(workflow["6"]["inputs"]["sampler_name"], "euler")
        self.assertEqual(workflow["8"]["inputs"]["filename_prefix"], "Froja/QwenImage21")

    def test_character_transform_uses_qwen_21_multi_reference_edit(self):
        original = backend.save_face_upload
        backend.save_face_upload = lambda _data, label: f"{label}.png"
        try:
            workflow = backend.build_character_transform_workflow({
                "source_image": "source-data",
                "reference_image": "body-data",
                "environment_image": "room-data",
                "instruction": "put the subject in the referenced pose",
                "preserve": "face identity and clothing",
                "transparent": True,
                "width": 1024,
                "height": 1024,
            })
        finally:
            backend.save_face_upload = original
        self.assertEqual(workflow["4"]["inputs"]["unet_name"], "qwen_image_2.1_int8_convrot.safetensors")
        self.assertEqual(workflow["5"]["inputs"]["clip_name"], "qwen3vl_8b_int8_convrot.safetensors")
        self.assertEqual(workflow["6"]["inputs"]["vae_name"], "qwen_image_2.1_vae_bf16.safetensors")
        self.assertEqual(workflow["7"]["class_type"], "TextEncodeQwenImage21")
        self.assertEqual(workflow["7"]["inputs"]["images.image_1"], ["1", 0])
        self.assertEqual(workflow["7"]["inputs"]["images.image_2"], ["2", 0])
        self.assertEqual(workflow["7"]["inputs"]["images.image_3"], ["3", 0])
        self.assertEqual(workflow["8"]["inputs"]["latent_image"], ["7", 2])
        self.assertIn("true transparent alpha background", workflow["7"]["inputs"]["prompt"])
        self.assertEqual(workflow["10"]["inputs"]["filename_prefix"], "Froja/QwenImage21Edit")

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

    def test_krea_reference_edit_uses_reference_latent_and_active_model(self):
        original = backend.save_face_upload
        backend.save_face_upload = lambda _data, _prefix: "froja-reference.png"
        try:
            workflow = backend.build_image_tool_workflow({
                "mode": "krea2-reference",
                "checkpoint": "krea2_turbo-Q4_K_S.gguf",
                "prompt": "turn the illustrated character into a realistic studio photograph",
                "source_image": "data:image/png;base64,unused",
                "width": 768,
                "height": 1024,
                "seed": 12,
                "strength": 0.72,
                "loras": [{"name": "detailer.safetensors", "strength": 0.6}],
            })
        finally:
            backend.save_face_upload = original
        self.assertEqual(workflow["1"]["class_type"], "UnetLoaderGGUF")
        self.assertEqual(workflow["2"]["inputs"]["type"], "krea2")
        self.assertEqual(workflow["5"]["class_type"], "TextEncodeKrea2OstrisEdit")
        self.assertEqual(workflow["5"]["inputs"]["image1"], ["4", 0])
        self.assertEqual(workflow["7"]["inputs"]["reference_latents_method"], "index_timestep_zero")
        self.assertEqual(workflow["9"]["inputs"]["width"], 768)
        self.assertEqual(workflow["10"]["class_type"], "Krea2OstrisEditModelPatch")
        self.assertEqual(workflow["20"]["inputs"]["lora_name"], "krea-detail-enhancer-exp.safetensors")
        self.assertEqual(workflow["20"]["inputs"]["strength_model"], 0.72)
        self.assertEqual(workflow["21"]["inputs"]["lora_name"], "detailer.safetensors")
        self.assertEqual(workflow["30"]["inputs"]["latent_image"], ["9", 0])
        self.assertEqual(workflow["30"]["inputs"]["denoise"], 1.0)
        self.assertEqual(workflow["32"]["inputs"]["filename_prefix"], "Froja/Krea2Reference")
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



class MaterialNameTests(unittest.TestCase):
    def test_technical_pbr_maps_are_hidden_and_names_cleaned(self):
        self.assertEqual(backend.material_display_name("fabric_leather_02_diff_4k"), "Fabric Leather 02")
        self.assertEqual(backend.material_display_name("GothicCommode_01_diff_4k"), "Gothic Commode 01")
        self.assertEqual(backend.material_display_name("rusty_metal_04_diff_4k"), "Rusty Metal 04")
        for stem in ("fabric_leather_02_ao_4k", "rusty_metal_04_arm_4k", "rusty_metal_04_metal_4k",
                     "fabric_leather_02_nor_gl_4k", "GothicCommode_01_roughness_4k", "rusty_metal_04_disp_4k"):
            self.assertIsNone(backend.material_display_name(stem), stem)
        self.assertEqual(backend.material_display_name("brushed_metal"), "Brushed Metal")
        self.assertEqual(backend.material_display_name("slumped_mortar_brick"), "Slumped Mortar Brick")



class SystemAdviceTests(unittest.TestCase):
    def test_advice_warns_about_full_ram_hot_gpu_and_full_drive(self):
        advice = backend.system_advice({
            "ram": {"percent": 96},
            "gpus": [{"temp": 86}],
            "cpu": {"temp": 30, "temp_source": "board"},
            "drives": [{"name": "C:", "free_gb": 9, "percent": 99}, {"name": "G:", "free_gb": 5000, "percent": 20}],
        })
        texts = " ".join(item["text"] for item in advice)
        self.assertIn("RAM", texts)
        self.assertIn("hot", texts)
        self.assertIn("Drive C: is almost full", texts)
        self.assertNotIn("Drive G:", texts)
        self.assertIn("LibreHardwareMonitor", texts)

    def test_quiet_system_gives_no_warnings(self):
        advice = backend.system_advice({"ram": {"percent": 40}, "gpus": [{"temp": 45}],
                                        "cpu": {"temp": 50, "temp_source": "cpu"}, "drives": [{"name": "D:", "free_gb": 900, "percent": 50}]})
        self.assertEqual(advice, [])



class MiniMaxVideoTests(unittest.TestCase):
    def test_gpu_tiers_are_plain_and_safe(self):
        self.assertFalse(backend.minimax_gpu_tier(8)["supported"])
        self.assertEqual(backend.minimax_gpu_tier(12)["tier"], "safe")
        self.assertEqual(backend.minimax_gpu_tier(12)["max_seconds"], 3)
        self.assertEqual(backend.minimax_gpu_tier(16)["tier"], "good")
        self.assertEqual(backend.minimax_gpu_tier(24)["tier"], "best")

    def test_frame_counts_follow_the_17k_plus_5_grid(self):
        for seconds in (1, 3, 4, 5):
            self.assertEqual((backend.minimax_frames(seconds) - 5) % 17, 0)
        self.assertEqual(backend.minimax_frames(3), 73)

    def test_workflow_uses_picture_only_for_image_mode(self):
        text = backend.minimax_workflow("a cat", 640, 352, 73, None, 1, "video/x")
        image = backend.minimax_workflow("a cat", 640, 352, 73, "pic.png", 1, "video/x")
        self.assertNotIn("6", text)
        self.assertNotIn("first_frame", text["8"]["inputs"])
        self.assertEqual(image["8"]["inputs"]["first_frame"], ["6", 0])
        self.assertEqual(image["2"]["class_type"], "MiniMaxH3TurboLoRA")

    def test_job_is_refused_while_switched_off(self):
        original = backend.minimax_video_enabled
        backend.minimax_video_enabled = lambda: False
        try:
            with self.assertRaises(PermissionError):
                backend.start_minimax_job({"prompt": "test"})
        finally:
            backend.minimax_video_enabled = original



class OllamaReleaseTests(unittest.TestCase):
    def test_unload_releases_every_loaded_model_even_if_one_fails(self):
        calls = []
        def fake(path, data=None, timeout=180):
            if path == "/api/ps":
                return {"models": [{"name": "qwen3.5:4b", "size_vram": 3}, {"name": "qwen3-vl:4b", "size_vram": 0}, {"name": "broken", "size_vram": 1}]}
            calls.append(data["model"])
            if data["model"] == "broken":
                raise OSError("boom")
            return {}
        original = backend.ollama_request
        backend.ollama_request = fake
        try:
            self.assertEqual(backend.unload_ollama_models(), ["qwen3.5:4b", "qwen3-vl:4b"])
            self.assertEqual(calls, ["qwen3.5:4b", "qwen3-vl:4b", "broken"])
        finally:
            backend.ollama_request = original



class LightStageTests(unittest.TestCase):
    def _sides(self, lights):
        import numpy as np
        image = np.asarray(backend.render_light_map(lights, 5, 120, 120)).astype(float).mean(axis=2)
        return image[:, :40].mean(), image[:, -40:].mean(), image[:40].mean(), image[-40:].mean()

    def test_light_lands_where_it_was_placed(self):
        left, right, _, _ = self._sides([{"azimuth": 270, "elevation": 20}])
        self.assertGreater(left, right * 2)
        left, right, _, _ = self._sides([{"azimuth": 90, "elevation": 20}])
        self.assertGreater(right, left * 2)
        _, _, top, bottom = self._sides([{"azimuth": 0, "elevation": 80}])
        self.assertGreater(top, bottom * 2)

    def test_lights_are_validated_and_described(self):
        lights = backend.clean_lights([{"azimuth": 450, "elevation": 200, "intensity": 500}, {"on": False}, {}, {}, {}])
        self.assertEqual(len(lights), 2)  # only the first three are read, and the switched-off one is skipped
        self.assertEqual(lights[0]["azimuth"], 90)
        self.assertEqual(lights[0]["elevation"], 85)
        self.assertEqual(lights[0]["intensity"], 100)
        text = backend.describe_lights([{"name": "Key", "azimuth": 280, "elevation": 15, "color": "#ff4fd8"}])
        self.assertIn("pink", text)
        self.assertIn("from the left", text)

    def test_relight_workflow_uses_the_light_map(self):
        import base64
        source = "data:image/png;base64," + base64.b64encode((backend.ROOT / "public" / "froja-mark.png").read_bytes()).decode()
        with tempfile.TemporaryDirectory() as folder, patch.object(backend, "COMFY_ROOT", Path(folder)):
            workflow = backend.build_relight_workflow({"source_image": source, "lights": [{"azimuth": 270}]})
            plain = backend.build_relight_workflow({"source_image": source, "direction": "left"})
        self.assertEqual(workflow["7"]["inputs"]["pixels"], ["12", 0])
        self.assertEqual(workflow["12"]["class_type"], "LoadImage")
        self.assertNotIn("12", plain)



class LocalConfigTests(unittest.TestCase):
    def test_settings_saved_with_a_bom_are_still_read(self):
        import codecs
        import os
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.local.json"
            path.write_bytes(codecs.BOM_UTF8 + json.dumps({"comfy_root": "C:/AI/ComfyUI"}).encode("utf-8"))
            previous = os.environ.get("FROJA_CONFIG")
            os.environ["FROJA_CONFIG"] = str(path)
            try:
                self.assertEqual(backend.load_local_config()["comfy_root"], "C:/AI/ComfyUI")
            finally:
                if previous is None:
                    os.environ.pop("FROJA_CONFIG", None)
                else:
                    os.environ["FROJA_CONFIG"] = previous

    def test_ollama_errors_are_explained(self):
        message = backend.ollama_error_message(404, b'{"error":"model \'qwen3-vl:4b\' not found"}')
        self.assertIn("not found", message)
        self.assertIn("ollama pull", message)
        odd = backend.ollama_error_message(425, b"")
        self.assertIn("425", odd)
        self.assertIn("VPN", odd)


if __name__ == "__main__":
    unittest.main()
