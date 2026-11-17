"""Audit member A's archived artifacts without altering their files.

Run from the repository root with Python 3.10+; every run creates a new folder.
This is an agent check, not a statement of either student's manual review.
"""

import csv
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
import PIL
from PIL import Image

from l0_smoothing.workflow import replay_record, _sha256_pixels


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with Image.open(path) as image:
        return np.array(image), image.mode


def load_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = Path(__file__).parent / ("audit-" + stamp)
    output.mkdir()
    summary = {
        "actor": "智能体执行验证；成员人工核验待完成",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, "results/member_b_verification/verify_existing.py"],
        "cwd": str(ROOT),
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "pillow": PIL.__version__, "opencv": cv2.__version__,
                        "platform": platform.platform()},
        "passed": False,
    }
    try:
        smooth = ROOT / "results/structure_smoothing/experiment-20261117T102719Z-1b827758b270"
        edges = ROOT / "results/edge_comparison/edges-20261117T105442Z-a63edf132bc2"
        manifest = json.loads((ROOT / "data/structure_smoothing/manifest.json").read_text(encoding="utf-8"))
        source_checks = []
        for name, item in manifest["images"].items():
            source = ROOT / "data/structure_smoothing/sources" / item["filename"]
            input_path = ROOT / item["input_file"]
            assert sha(source) == item["sha256"], f"source changed: {source}"
            assert sha(input_path) == item["input_sha256"], f"input changed: {input_path}"
            source_checks.append({"image": name, "source_sha256": sha(source),
                                  "input_sha256": sha(input_path), "passed": True})
        summary["source_checks"] = source_checks
        rows = load_csv(smooth / "runs.csv")
        expected = {(name, lam, kappa) for name in manifest["images"]
                    for lam in (0.005, 0.02, 0.08) for kappa in (1.5, 2.0)}
        assert len(rows) == 18
        assert {(r["image"], float(r["lambda"]), float(r["kappa"])) for r in rows} == expected
        audits = []
        for row in rows:
            record_path = smooth / row["record"]
            record = json.loads(record_path.read_text(encoding="utf-8"))
            original, mode = read(record_path.parent / record["input"]["copy"])
            floats = np.load(smooth / row["float_result"], allow_pickle=False)
            display, display_mode = read(smooth / row["display_result"])
            assert sha(record_path.parent / record["input"]["copy"]) == record["input"]["file_sha256"]
            assert _sha256_pixels(original, mode) == record["input"]["pixel_sha256"]
            assert sha(ROOT / row["input"]) == record["input"]["file_sha256"]
            assert floats.dtype == np.float64 and np.isfinite(floats).all()
            assert list(floats.shape) == record["output"]["shape"] == record["input"]["shape"]
            assert display_mode == mode == record["input"]["mode"]
            assert np.array_equal(display, np.rint(np.clip(floats, 0, 1) * 255).astype(np.uint8))
            assert _sha256_pixels(display, mode) == record["output"]["display_pixel_sha256"]
            assert record["parameters"] == {"lambda": float(row["lambda"]),
                                             "kappa": float(row["kappa"]), "beta_max": 1e5}
            assert int(row["iterations"]) == record["iterations"]
            assert float(row["elapsed_seconds"]) == record["elapsed_seconds"]
            delta = float(np.mean(np.abs(floats - original.astype(np.float64) / 255)))
            assert abs(delta - float(row["mean_abs_change"])) <= 1e-12
            audits.append({"image": row["image"], **record["parameters"],
                           "iterations": record["iterations"],
                           "original_elapsed_seconds": record["elapsed_seconds"],
                           "mean_abs_change": delta,
                           "record": str(record_path.relative_to(ROOT)), "passed": True})
        summary["smooth_audit"] = audits
        edge_rows = load_csv(edges / "edges.csv")
        assert len(edge_rows) == 21
        edge_audits = []
        for row in edge_rows:
            source = ROOT / row["source_image"]
            assert sha(source) == row["source_sha256"]
            pixels, mode = read(source)
            assert mode == row["source_mode"]
            gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY) if mode == "RGB" else pixels
            assert (float(row["low_threshold"]), float(row["high_threshold"]),
                    int(row["aperture_size"]), row["l2_gradient"]) == (60, 120, 3, "True")
            assert gray.shape == (int(row["height"]), int(row["width"]))
            assert (int(gray.min()), int(gray.max())) == (int(row["gray_min"]), int(row["gray_max"]))
            assert hashlib.sha256(gray.tobytes()).hexdigest() == row["grayscale_sha256"]
            recomputed = cv2.Canny(gray, 60, 120, apertureSize=3, L2gradient=True)
            stored, stored_mode = read(ROOT / row["edge_path"])
            assert stored_mode == "L" and np.array_equal(recomputed, stored)
            assert hashlib.sha256(stored.tobytes()).hexdigest() == row["edge_sha256"]
            assert np.count_nonzero(stored) == int(row["edge_pixels"])
            edge_audits.append({"image": row["image"], "kind": row["kind"],
                                "lambda": row["lambda"], "kappa": row["kappa"],
                                "edge_pixels": int(row["edge_pixels"]), "passed": True})
        summary["edge_audit"] = edge_audits
        panels = []
        for name in manifest["images"]:
            smooth_roi = json.loads((smooth / name / "roi.json").read_text(encoding="utf-8"))["xyxy"]
            edge_roi = json.loads((edges / name / "roi.json").read_text(encoding="utf-8"))["xyxy"]
            assert smooth_roi == edge_roi
            for parent, filenames in ((smooth, ("full_comparison.png", "same_region_zoom.png")),
                                      (edges, ("full_edge_comparison.png", "same_region_edge_zoom.png"))):
                for filename in filenames:
                    panel = parent / name / filename
                    with Image.open(panel) as image:
                        image.verify()
                    panels.append(str(panel.relative_to(ROOT)))
        summary["decodable_panels_and_matched_rois"] = panels
        selected = {"beach": (0.005, 1.5), "brick_window_gray": (0.02, 2.0),
                    "sunflower": (0.08, 1.5)}
        replays = []
        for row in rows:
            if selected[row["image"]] != (float(row["lambda"]), float(row["kappa"])):
                continue
            replay_path, passed = replay_record(smooth / row["record"], output)
            record = json.loads(replay_path.read_text(encoding="utf-8"))
            replays.append({"image": row["image"], "mode": record["input"]["mode"],
                            "record": str(replay_path.relative_to(ROOT)), "passed": passed,
                            "elapsed_seconds": record["elapsed_seconds"],
                            "comparison": record["comparison"]})
        summary["replays"] = replays
        summary["passed"] = len(replays) == 3 and all(item["passed"] for item in replays)
        summary["notes"] = [
            "Archived Windows source_path strings are informational: replay uses input copies next to run.json.",
            "Source licensing is copied from archived metadata; no new online license verification was performed.",
            "12 panel PNGs decode and ROI coordinates match; this alone does not verify visual quality or labels.",
            "Only selected three smoothing results were recomputed; all 18 saved float/display pairs were audited.",
            "Original execution time is not a current-machine benchmark; new replay times are separately recorded.",
        ]
    except Exception as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        (output / "audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(output / "audit.json")
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
