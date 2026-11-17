"""CLI checks with tiny synthetic grayscale/RGB PNGs and Chinese paths."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, PngImagePlugin

from l0_smoothing.workflow import _save_run, read_8bit_image


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "l0_smoothing", *map(str, args)],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def _record_from_output(process: subprocess.CompletedProcess[str]) -> tuple[Path, dict]:
    record_path = Path(process.stdout.strip())
    return record_path, json.loads(record_path.read_text(encoding="utf-8"))


class WorkflowTests(unittest.TestCase):
    def test_display_clipping_does_not_change_saved_float_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "中文路径"
            root.mkdir()
            input_path = root / "灰度.png"
            input_pixels = np.array([[0, 255]], dtype=np.uint8)
            Image.fromarray(input_pixels).save(input_path)
            raw_result = np.array([[-0.25, 1.25]], dtype=np.float64)
            result = SimpleNamespace(
                image=raw_result,
                parameters={"lambda": 0.02, "kappa": 2.0, "beta_max": 1e5},
                iterations=1,
                elapsed_seconds=0.0,
            )
            record_path = _save_run(
                input_path, root / "结果", "run", "L", input_pixels, result
            )
            record = json.loads(record_path.read_text(encoding="utf-8"))
            np.testing.assert_array_equal(
                np.load(record_path.parent / record["output"]["float"]), raw_result
            )
            with Image.open(record_path.parent / record["output"]["display"]) as display:
                np.testing.assert_array_equal(np.asarray(display), [[0, 255]])
            np.testing.assert_array_equal(result.image, raw_result)

    def test_grayscale_read_save_replay_and_new_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "中文路径"
            root.mkdir()
            input_path = root / "灰度样例.png"
            pixels = np.array([[0, 64, 255], [128, 192, 32]], dtype=np.uint8)
            Image.fromarray(pixels).save(input_path)
            output_parent = root / "保存结果"

            normalized, loaded, mode = read_8bit_image(input_path)
            self.assertEqual(mode, "L")
            np.testing.assert_array_equal(loaded, pixels)
            np.testing.assert_array_equal(normalized, pixels.astype(np.float64) / 255)

            command = (
                "run", input_path, "--output-dir", output_parent,
                "--lambda", "0.02", "--kappa", "2", "--beta-max", "0.16",
            )
            first = _cli(*command)
            self.assertEqual(first.returncode, 0, first.stderr)
            first_path, record = _record_from_output(first)
            self.assertEqual(record["kind"], "run")
            self.assertEqual(record["parameters"], {
                "lambda": 0.02, "kappa": 2.0, "beta_max": 0.16,
            })
            self.assertEqual(record["iterations"], 2)
            self.assertGreaterEqual(record["elapsed_seconds"], 0)
            self.assertIn("python", record["environment"])
            self.assertIn("numpy", record["environment"])
            self.assertIn("pillow", record["environment"])
            self.assertEqual(
                (first_path.parent / record["input"]["copy"]).read_bytes(),
                input_path.read_bytes(),
            )
            floats = np.load(first_path.parent / record["output"]["float"])
            self.assertEqual(floats.dtype, np.float64)
            self.assertEqual(floats.shape, pixels.shape)
            with Image.open(first_path.parent / record["output"]["display"]) as display:
                self.assertEqual(display.mode, "L")
                np.testing.assert_array_equal(
                    np.asarray(display),
                    np.rint(np.clip(floats, 0, 1) * 255).astype(np.uint8),
                )

            replay = _cli("replay", first_path, "--output-dir", output_parent)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            replay_path, replay_data = _record_from_output(replay)
            self.assertNotEqual(first_path, replay_path)
            self.assertTrue(replay_data["comparison"]["passed"])
            self.assertEqual(replay_data["comparison"]["different_pixel_count"], 0)
            self.assertLessEqual(replay_data["comparison"]["max_float_abs_error"], 1e-12)

            second = _cli(*command)
            self.assertEqual(second.returncode, 0, second.stderr)
            second_path, _ = _record_from_output(second)
            self.assertNotEqual(first_path.parent, second_path.parent)
            self.assertTrue(first_path.exists())
            self.assertTrue(replay_path.exists())

    def test_rgb_reencoded_pngs_match_by_pixels_and_changed_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "含中文的目录"
            root.mkdir()
            input_path = root / "彩色样例.png"
            pixels = np.array(
                [[[0, 32, 255], [128, 64, 16], [255, 0, 96]],
                 [[12, 220, 44], [80, 150, 240], [200, 10, 100]]],
                dtype=np.uint8,
            )
            Image.fromarray(pixels).save(input_path)
            output_parent = root / "结果"
            run = _cli(
                "run", input_path, "--output-dir", output_parent,
                "--lambda", "0.03", "--kappa", "3", "--beta-max", "0.54",
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            run_path, run_data = _record_from_output(run)
            self.assertEqual(run_data["input"]["mode"], "RGB")
            self.assertEqual(run_data["iterations"], 2)

            display_path = run_path.parent / run_data["output"]["display"]
            original_bytes = display_path.read_bytes()
            with Image.open(display_path) as image:
                metadata = PngImagePlugin.PngInfo()
                metadata.add_text("reencoded", "same decoded pixels")
                image.save(display_path, pnginfo=metadata, compress_level=0)
            self.assertNotEqual(display_path.read_bytes(), original_bytes)
            replay = _cli("replay", run_path, "--output-dir", output_parent)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            _, replay_data = _record_from_output(replay)
            self.assertTrue(replay_data["comparison"]["display_pixels_equal"])
            self.assertEqual(replay_data["comparison"]["different_pixel_count"], 0)

            equivalent_input = root / "同像素不同编码.png"
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text("source", "different PNG bytes")
            Image.fromarray(pixels).save(equivalent_input, pnginfo=metadata)
            self.assertNotEqual(equivalent_input.read_bytes(), input_path.read_bytes())
            same_pixels = _cli(
                "replay", run_path, "--output-dir", output_parent,
                "--input", equivalent_input,
            )
            self.assertEqual(same_pixels.returncode, 0, same_pixels.stderr)
            _, same_data = _record_from_output(same_pixels)
            self.assertTrue(same_data["comparison"]["passed"])
            self.assertFalse(same_data["comparison"]["input_file_bytes_equal"])

            changed = pixels.copy()
            changed[0, 0, 0] = 1
            changed_input = root / "像素改变.png"
            Image.fromarray(changed).save(changed_input)
            rejected = _cli("replay", run_path, "--input", changed_input)
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("input decoded pixels differ", rejected.stderr)

    def test_replay_reports_display_and_float_mismatches(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "中文"
            root.mkdir()
            input_path = root / "灰度.png"
            Image.fromarray(np.array([[0, 255], [64, 128]], dtype=np.uint8)).save(input_path)
            run = _cli("run", input_path, "--output-dir", root, "--beta-max", "0.16")
            self.assertEqual(run.returncode, 0, run.stderr)
            run_path, record = _record_from_output(run)
            display_path = run_path.parent / record["output"]["display"]
            with Image.open(display_path) as image:
                original = np.array(image)
            changed = original.copy()
            changed[0, 0] = 1 if changed[0, 0] != 1 else 2
            Image.fromarray(changed).save(display_path)
            pixel_failure = _cli("replay", run_path, "--output-dir", root)
            self.assertEqual(pixel_failure.returncode, 1)
            _, pixel_data = _record_from_output(pixel_failure)
            self.assertFalse(pixel_data["comparison"]["passed"])
            self.assertEqual(pixel_data["comparison"]["different_pixel_count"], 1)
            self.assertTrue(pixel_data["comparison"]["float_within_tolerance"])

            Image.fromarray(original).save(display_path)
            float_path = run_path.parent / record["output"]["float"]
            floats = np.load(float_path)
            floats[0, 0] += 0.001
            np.save(float_path, floats)
            float_failure = _cli("replay", run_path, "--output-dir", root)
            self.assertEqual(float_failure.returncode, 1)
            _, float_data = _record_from_output(float_failure)
            self.assertFalse(float_data["comparison"]["passed"])
            self.assertGreater(float_data["comparison"]["max_float_abs_error"], 1e-12)
            self.assertTrue(float_data["comparison"]["display_pixels_equal"])


if __name__ == "__main__":
    unittest.main()
