"""Independent PSNR/SSIM check of actual JPEG experiment pixels.

Uses NumPy valid separable convolution; deliberately does not import the
experiment's metrics module or use OpenCV's filtering implementation.
"""

import csv
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import PIL
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = ROOT / "results/jpeg_artifacts/jpeg-20261117T155122Z-e37cd961efa5"


def read(path):
    with Image.open(path) as image:
        return np.array(image, dtype=np.float64)


def valid_gaussian(array):
    axis = np.arange(-5, 6, dtype=np.float64)
    kernel = np.exp(-axis ** 2 / (2 * 1.5 ** 2))
    kernel /= kernel.sum()
    vertical = np.lib.stride_tricks.sliding_window_view(array, 11, axis=0)
    vertical = np.sum(vertical * kernel, axis=-1)
    horizontal = np.lib.stride_tricks.sliding_window_view(vertical, 11, axis=1)
    return np.sum(horizontal * kernel, axis=-1)


def compute(a, b):
    mse = float(np.mean((a - b) ** 2))
    psnr = float(10 * np.log10(255 ** 2 / mse)) if mse else float("inf")
    ma, mb = valid_gaussian(a), valid_gaussian(b)
    va = valid_gaussian(a * a) - ma * ma
    vb = valid_gaussian(b * b) - mb * mb
    cov = valid_gaussian(a * b) - ma * mb
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    score = ((2 * ma * mb + c1) * (2 * cov + c2)) / (
        (ma * ma + mb * mb + c1) * (va + vb + c2))
    return psnr, float(np.mean(score))


def main():
    with (EXPERIMENT / "metrics.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 30
    expected = {(name, quality, lam) for name in ("house_rgb", "line_gray")
                for quality in (10, 30, 70) for lam in (None, .0005, .002, .008, .03)}
    observed = {(r["image"], int(r["jpeg_quality"]), float(r["lambda"]) if r["lambda"] else None)
                for r in rows}
    assert expected == observed
    manifest = json.loads((EXPERIMENT / "source_manifest.json").read_text(encoding="utf-8"))
    checks, baseline = [], {}
    max_psnr_error = max_ssim_error = 0.0
    for row in rows:
        name, quality = row["image"], int(row["jpeg_quality"])
        clean_path = EXPERIMENT / name / "clean.png"
        assert hashlib.sha256(clean_path.read_bytes()).hexdigest() == manifest["images"][name]["file_sha256"]
        clean = read(clean_path)
        candidate = read(EXPERIMENT / row["display_result"])
        assert clean.shape == candidate.shape
        roi = json.loads((EXPERIMENT / name / "roi.json").read_text(encoding="utf-8"))["xyxy"]
        assert roi == manifest["images"][name]["roi_xyxy"]
        x0, y0, x1, y1 = roi
        p, s = compute(clean, candidate)
        rp, rs = compute(clean[y0:y1, x0:x1], candidate[y0:y1, x0:x1])
        values = {"psnr_db": p, "ssim": s, "roi_psnr_db": rp, "roi_ssim": rs}
        errors = {key: abs(value - float(row[key])) for key, value in values.items()}
        assert all(error <= 1e-10 for error in errors.values()), errors
        max_psnr_error = max(max_psnr_error, errors["psnr_db"], errors["roi_psnr_db"])
        max_ssim_error = max(max_ssim_error, errors["ssim"], errors["roi_ssim"])
        if row["stage"] == "jpeg":
            baseline[(name, quality)] = values
        else:
            original = baseline[(name, quality)]
            assert abs(p - original["psnr_db"] - float(row["delta_psnr_db"])) <= 1e-10
            assert abs(s - original["ssim"] - float(row["delta_ssim"])) <= 1e-10
        checks.append({"image": name, "quality": quality, "stage": row["stage"],
                       "lambda": float(row["lambda"]) if row["lambda"] else None,
                       "roi_xyxy": roi, "recomputed": values, "absolute_errors": errors,
                       "passed": True})
    summary = {
        "actor": "智能体独立核对；成员B 蒋天乐 2023010721；非成员人工核验",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, str(Path(__file__).relative_to(ROOT))],
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pillow": PIL.__version__},
        "experiment": str(EXPERIMENT.relative_to(ROOT)),
        "metrics_csv_sha256": hashlib.sha256((EXPERIMENT / "metrics.csv").read_bytes()).hexdigest(),
        "independence": "NumPy Gaussian weights and valid separable convolution; no cv2 filtering or l0_smoothing.metrics import",
        "protocol": "uint8 decoded pixels; data_range=255; 11x11 Gaussian sigma1.5; population moments; valid centres only; RGB channel average; ROI separately cropped before metric",
        "rows_checked": len(checks), "max_psnr_abs_error_db": max_psnr_error,
        "max_ssim_abs_error": max_ssim_error,
        "negative_psnr_runs": sum(r["stage"] == "l0" and float(r["delta_psnr_db"]) < 0 for r in rows),
        "negative_ssim_runs": sum(r["stage"] == "l0" and float(r["delta_ssim"]) < 0 for r in rows),
        "checks": checks, "passed": True,
    }
    output = Path(__file__).with_name("metrics_audit.json")
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "checks"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
