import ast
import base64
import io
import json
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest.mock import Mock, patch

from PIL import Image

import animate
import backend


class CameraPathTests(unittest.TestCase):
    def test_orbit_orders_angles_and_closes_at_360(self):
        keys = animate.camera_path("orbit", [315, 90, 270, 45, 180, 0, 225, 135, -45, 360])
        self.assertEqual([key["azimuth"] for key in keys], list(range(0, 361, 45)))
        self.assertEqual([key["t"] for key in keys], [round(i * 0.6, 2) for i in range(9)])
        self.assertEqual({key["distance"] for key in keys}, {animate.CAMERA_DISTANCE})

    def test_sparse_orbit_includes_front_and_scales_time_by_angle(self):
        keys = animate.camera_path("orbit", [315, 90, 450, -90])
        self.assertEqual([key["azimuth"] for key in keys], [0, 90, 270, 315, 360])
        self.assertEqual([key["t"] for key in keys], [0, 1.2, 3.6, 4.2, 4.8])

    def test_bullet_time_holds_front_then_orbits_faster(self):
        angles = [270, 180, 90, 0]
        keys = animate.camera_path("bullet-time", angles)
        self.assertEqual([key["azimuth"] for key in keys], [0, 0, 90, 180, 270, 360])
        self.assertGreater(keys[1]["t"], 0)
        self.assertLess(keys[-1]["t"], animate.camera_path("orbit", angles)[-1]["t"])
        self.assertGreater(keys[2]["t"] - keys[1]["t"], keys[3]["t"] - keys[2]["t"])
        self.assertTrue(all(a["t"] < b["t"] for a, b in zip(keys, keys[1:])))

    def test_orbit_honors_explicit_duration(self):
        keys = animate.camera_path("orbit", [90, 180, 270], seconds=10)
        self.assertEqual([key["t"] for key in keys], [0, 2.5, 5, 7.5, 10])

    def test_push_in_reduces_distance_and_preserves_direction(self):
        keys = animate.camera_path("push-in", seconds=3)
        self.assertEqual([key["t"] for key in keys], [0, 3])
        self.assertEqual([key["azimuth"] for key in keys], [0, 0])
        self.assertEqual([key["zoom"] for key in keys], [1, 1.12])
        self.assertGreater(keys[0]["distance"], keys[1]["distance"])

    def test_crane_rises_and_zooms_slightly(self):
        keys = animate.camera_path("crane")
        self.assertEqual([key["t"] for key in keys], [0, 5])
        self.assertEqual([key["azimuth"] for key in keys], [0, 0])
        self.assertLess(keys[0]["elevation"], 0)
        self.assertGreater(keys[1]["elevation"], 0)
        self.assertGreater(keys[1]["zoom"], keys[0]["zoom"])

    def test_blender_script_is_self_contained(self):
        script = animate.blender_script(animate.camera_path("orbit", [90, 180, 270]))
        tree = ast.parse(script)
        self.assertIn("Froja Camera", script)
        self.assertIn("keyframe_insert", script)
        self.assertIn("FPS = 30", script)
        for literal in ast.walk(tree):
            if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                self.assertFalse(PurePosixPath(literal.value).is_absolute())
                self.assertFalse(PureWindowsPath(literal.value).is_absolute())


class AnimateRouteTests(unittest.TestCase):
    def post(self, payload):
        body = json.dumps(payload).encode()
        handler = Mock()
        handler.path = "/api/animate"
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile, handler.wfile = io.BytesIO(body), io.BytesIO()
        backend.FrojaHandler.do_POST(handler)
        return handler.send_response.call_args.args[0], json.loads(handler.wfile.getvalue())

    def test_invalid_mode_or_preset_returns_400_before_queueing(self):
        for payload in ({"mode": "video"}, {"mode": "camera", "preset": "dolly"}):
            with self.subTest(payload=payload), patch.object(animate, "start_job") as start_job:
                status, result = self.post(payload)
                self.assertEqual(status, 400)
                self.assertIn("error", result)
                start_job.assert_not_called()

    def test_running_animation_returns_409(self):
        with patch.object(animate, "validate_request", return_value={"mode": "life"}), \
                patch.object(animate, "_jobs", {"existing": Mock(status="running")}):
            status, result = self.post({"mode": "life"})
        self.assertEqual(status, 409)
        self.assertIn("already running", result["error"])

    def test_real_requires_an_image_before_checking_h3(self):
        with patch.object(backend, "minimax_status") as h3_status, patch.object(animate, "start_job") as start_job:
            status, result = self.post({"mode": "real"})
        self.assertEqual(status, 400)
        self.assertIn("Master picture", result["error"])
        h3_status.assert_not_called()
        start_job.assert_not_called()

    def test_real_explains_how_to_enable_h3(self):
        with patch.object(backend, "minimax_status", return_value={"enabled": False}), \
                patch.object(animate, "start_job") as start_job:
            status, result = self.post({"mode": "real", "image": self.image()})
        self.assertEqual(status, 400)
        self.assertIn("MiniMax H3 is switched off", result["error"])
        self.assertIn("Animate", result["error"])
        start_job.assert_not_called()

    def test_real_queues_defaults_and_enforces_h3_tier_duration(self):
        image = self.image()
        with patch.object(backend, "minimax_status", return_value={
            "enabled": True, "installed": True, "supported": True, "max_seconds": 3,
        }), patch.object(animate, "start_job", return_value=Mock(id="real-job")) as start_job:
            status, result = self.post({"mode": "real", "image": image})
            self.assertEqual(status, 202)
            self.assertEqual(result["job_id"], "real-job")
            self.assertEqual(start_job.call_args.args[1], dict(
                mode="real", source=image, prompt=animate.REAL_PROMPT, sound=animate.REAL_SOUND, seconds=3,
            ))
            status, result = self.post({"mode": "real", "image": image, "seconds": 4})
            self.assertEqual(status, 400)
            self.assertIn("up to 3 seconds", result["error"])
            start_job.assert_called_once()

    @staticmethod
    def image():
        png = io.BytesIO()
        Image.new("RGB", (2, 2)).save(png, format="PNG")
        return "data:image/png;base64," + base64.b64encode(png.getvalue()).decode()


class RealPostProcessTests(unittest.TestCase):
    def test_lanczos_doubles_size_and_keeps_24_fps(self):
        args = animate.real_encode_args(Path("h3.mp4"), Path("animation.mp4"), has_audio=False)
        self.assertEqual(args[args.index("-vf") + 1], "fps=24:start_time=0,scale=iw*2:ih*2:flags=lanczos")
        self.assertEqual(args[args.index("-crf") + 1], "20")
        self.assertEqual(args[args.index("-preset") + 1], "medium")
        self.assertEqual(args[args.index("-pix_fmt") + 1], "yuv420p")
        self.assertEqual(args[args.index("-c:v") + 1], "libx264")
        self.assertEqual(args[args.index("-movflags") + 1], "+faststart")
        self.assertEqual(args.count("-map"), 1)
        self.assertNotIn("0:a:0", args)
        self.assertNotIn("-af", args)

    def test_real_esrgan_frames_use_original_sound_with_loudness_normalization(self):
        source = Path("h3.mp4")
        frames = Path("upscaled") / "%05d.png"
        extraction = animate.real_extract_args(source, Path("original") / "%05d.png")
        self.assertIn("fps=24:start_time=0", extraction)
        args = animate.real_encode_args(source, Path("animation.mp4"), has_audio=True, upscaled_frames=frames)
        self.assertEqual(args[:6], ["-i", str(source), "-framerate", "24", "-i", str(frames)])
        self.assertIn("1:v:0", args)
        self.assertIn("0:a:0", args)
        self.assertEqual(args[args.index("-af") + 1], "loudnorm=I=-16:TP=-1.5,apad")
        self.assertIn("-shortest", args)
        self.assertEqual(args[args.index("-c:a") + 1], "aac")
        self.assertEqual(args[args.index("-b:a") + 1], "192k")
        self.assertNotIn("-vf", args)
