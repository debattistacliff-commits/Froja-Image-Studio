import base64
import io
import unittest

from PIL import Image, ImageChops, ImageDraw

import backend


def picture_url():
    stream = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()


class WardrobeTests(unittest.TestCase):
    def test_reuses_qwen_edit_settings_with_two_images_and_no_camera_lora(self):
        graph = backend.build_wardrobe_workflow({"category": "top", "seed": 34}, "master.png", "crop.png")
        camera = backend.build_camera_view_workflow({"azimuth": 0, "seed": 34}, "master.png")
        for key in ("3", "6", "7", "8", "9", "13", "17"):
            self.assertEqual(graph[key], camera[key])
        self.assertEqual(graph["5"]["inputs"]["lora_name"], camera["5"]["inputs"]["lora_name"])
        self.assertEqual(graph["5"]["inputs"]["model"], ["3", 0])
        self.assertNotIn("4", graph)
        self.assertEqual(graph["1"]["inputs"]["image"], "master.png")
        self.assertEqual(graph["18"]["inputs"]["image"], "crop.png")
        self.assertEqual(graph["10"]["class_type"], "TextEncodeQwenImageEditPlus")
        self.assertEqual(graph["10"]["inputs"]["image1"], ["1", 0])
        self.assertEqual(graph["10"]["inputs"]["image2"], ["18", 0])
        self.assertNotIn("image3", graph["10"]["inputs"])

    def test_each_category_uses_item_target_and_preservation_instructions(self):
        cues = {
            "top": "Keep the trousers",
            "bottom": "Keep the top",
            "outfit": "in the outfit",
            "shoes": "on the feet",
            "hair": "the hairstyle",
            "accessory": "Fit",
            "material": "Keep the cut, seams and fit",
        }
        for category, cue in cues.items():
            with self.subTest(category=category):
                graph = backend.build_wardrobe_workflow({
                    "category": category, "item": "the custom item", "target": "the custom target",
                }, "master.png", "crop.png")
                prompt = graph["10"]["inputs"]["prompt"]
                for expected in (cue, "the custom item", "the custom target", "face", "pose", "image 1", "image 2"):
                    self.assertIn(expected, prompt)

    def test_defaults_include_outfit_material_and_accessory_placement(self):
        for category, target in {
            "top": "the shirt", "bottom": "the trousers", "outfit": "the clothes",
            "shoes": "the shoes", "hair": "the hair",
        }.items():
            self.assertEqual(backend.wardrobe_terms({"category": category})[2], target)
        self.assertEqual(backend.wardrobe_terms({"category": "material", "item": "the jacket"})[2], "the jacket")
        self.assertEqual(backend.wardrobe_terms({"category": "accessory", "item": "the scarf"})[2], "the neck")

    def test_long_sleeved_tops_also_replace_the_arms(self):
        self.assertEqual(backend.wardrobe_terms({"category": "top", "item": "the navy suit jacket"})[2], "the shirt and the arms")
        self.assertEqual(backend.wardrobe_terms({"category": "top", "item": "a red t-shirt"})[2], "the shirt")
        self.assertEqual(backend.wardrobe_terms({"category": "top", "item": "the hoodie", "target": "the vest"})[2], "the vest")

    def test_combined_replace_area_is_masked_part_by_part(self):
        self.assertEqual(backend.wardrobe_target_parts("the shirt and the arms"), ["the shirt", "the arms"])
        self.assertEqual(backend.wardrobe_target_parts("the shirt"), ["the shirt"])

    def test_suit_jacket_mask_can_exclude_the_matching_trousers(self):
        item = "the navy suit jacket"
        self.assertEqual(backend.wardrobe_reference_query("top", item), "jacket")
        self.assertEqual(backend.wardrobe_reference_query("outfit", item), item)

    def test_reference_trousers_match_the_visible_part_of_a_cropped_master(self):
        reference = Image.new("RGB", (64, 100), "red")
        ImageDraw.Draw(reference).rectangle((0, 38, 63, 99), fill="blue")
        mask = Image.new("L", reference.size)
        ImageDraw.Draw(mask).rectangle((16, 16, 47, 94), fill=255)
        target = Image.new("L", (64, 96))
        draw = ImageDraw.Draw(target)
        draw.rectangle((16, 76, 47, 95), fill=255)
        crop = backend.wardrobe_visible_bottom(reference, mask, target)
        self.assertEqual(crop.size, (48, 36))
        self.assertNotIn((0, 0, 255), set(crop.getdata()))
        draw.line((0, 95, 63, 95), fill=0)
        self.assertIsNone(backend.wardrobe_visible_bottom(reference, mask, target))
        workflow = backend.build_wardrobe_workflow(
            {"category": "bottom"}, "master.png", "crop.png", cropped_bottom_mask="trousers.png",
        )
        self.assertIn("continues through the bottom edge", workflow["10"]["inputs"]["prompt"])
        self.assertEqual(workflow["19"]["inputs"]["image"], "trousers.png")
        self.assertEqual(workflow["20"]["class_type"], "SetLatentNoiseMask")
        self.assertEqual(workflow["13"]["inputs"]["latent_image"], ["20", 0])
        self.assertLess(workflow["13"]["inputs"]["denoise"], 1)

    def test_validates_images_category_descriptions_and_seed(self):
        payload = {"category": "top", "person": picture_url(), "reference": picture_url(), "seed": 2**64 - 1}
        request = backend.validate_wardrobe(payload)
        self.assertEqual(request["person"].size, (32, 32))
        self.assertEqual(request["seed"], 2**64 - 1)
        for invalid in (
            {"category": ["top"]}, {"category": "face"}, {"seed": True}, {"seed": 2**64}, {"seed": -2},
            {"item": 7}, {"target": "x" * 201}, {"reference": None},
            {"person": "data:image/png;base64,aGVsbG8="}, {"reference": "data:image/png;base64,@@@@"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                backend.validate_wardrobe({**payload, **invalid})
        with self.assertRaises(ValueError):
            backend.validate_wardrobe([])

    def test_crop_masks_background_and_composite_preserves_face_and_other_pixels(self):
        original = Image.new("RGB", (64, 64), (220, 160, 70))
        target = Image.new("L", original.size)
        ImageDraw.Draw(target).rectangle((8, 8, 55, 55), fill=255)
        face = Image.new("L", original.size)
        ImageDraw.Draw(face).rectangle((20, 8, 40, 20), fill=255)
        crop = backend.wardrobe_reference_crop(original, ImageChops.subtract(target, face))
        self.assertEqual(crop.size, (64, 64))
        self.assertEqual(crop.getpixel((0, 0)), (128, 128, 128))
        self.assertEqual(crop.getpixel((25, 14)), (128, 128, 128))
        edited = Image.new("RGB", (32, 32), (50, 60, 180))
        result, matte = backend.wardrobe_composite(original, edited, target, face)
        self.assertEqual(result.size, original.size)
        self.assertIsNone(ImageChops.multiply(matte, face).getbbox())
        self.assertIsNone(ImageChops.multiply(matte, ImageChops.invert(target)).getbbox())
        self.assertIsNone(ImageChops.difference(result.crop(face.getbbox()), original.crop(face.getbbox())).getbbox())
        self.assertEqual(result.getpixel((32, 38)), edited.getpixel((0, 0)))


if __name__ == "__main__":
    unittest.main()
