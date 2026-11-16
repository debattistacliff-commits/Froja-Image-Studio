import tempfile
import unittest
from pathlib import Path

from PIL import Image, PngImagePlugin

import library_service


class LibraryStudioTests(unittest.TestCase):
    def test_indexes_metadata_without_changing_source(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as data:
            source = Path(folder) / "sample.png"
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text("parameters", "bronze knight in snow\nNegative prompt: blur\nSteps: 8, Sampler: Euler, CFG scale: 2.5, Seed: 42, Model: test-model")
            Image.new("RGB", (64, 48), "navy").save(source, pnginfo=metadata)
            before = source.read_bytes()
            original_db = library_service.DB_PATH
            library_service.DB_PATH = Path(data) / "library.sqlite3"
            try:
                result = library_service.scan_folders([Path(folder)])
                with library_service.connect() as db:
                    row = db.execute("SELECT * FROM images").fetchone()
                self.assertEqual(result["total"], 1)
                self.assertEqual((row["width"], row["height"]), (64, 48))
                self.assertEqual(row["prompt"], "bronze knight in snow")
                self.assertEqual(row["negative_prompt"], "blur")
                self.assertEqual(source.read_bytes(), before)
            finally:
                library_service.DB_PATH = original_db

    def test_missing_folder_is_safe(self):
        with tempfile.TemporaryDirectory() as data:
            original_db = library_service.DB_PATH
            library_service.DB_PATH = Path(data) / "library.sqlite3"
            try:
                result = library_service.scan_folders([Path(data) / "missing"])
                self.assertEqual(result, {"indexed": 0, "updated": 0, "total": 0})
            finally:
                library_service.DB_PATH = original_db


    def test_comfy_graph_fields(self):
        graph = {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z-image.safetensors"}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "bronze inventor"}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "blur, watermark"}},
            "9": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 8, "cfg": 1.5,
                    "sampler_name": "euler", "positive": ["5", 0], "negative": ["6", 0]}},
        }
        fields = library_service._comfy_fields(graph)
        self.assertEqual(fields["prompt"], "bronze inventor")
        self.assertEqual(fields["negative_prompt"], "blur, watermark")
        self.assertEqual(fields["model"], "z-image.safetensors")
        self.assertEqual(fields["seed"], "42")
        self.assertEqual(fields["steps"], "8")
        self.assertEqual(fields["cfg"], "1.5")
        self.assertEqual(fields["sampler"], "euler")


if __name__ == "__main__":
    unittest.main()
