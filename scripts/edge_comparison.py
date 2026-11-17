"""Compare Canny edges on archived inputs and all saved L0 display results.

Run from the repository root: python -m scripts.edge_comparison run/check ...
The smoothing algorithm is never rerun here.
"""

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import PIL
from PIL import Image

from scripts.structure_smoothing_experiment import KAPPAS, LAMBDAS, SOURCES, _panel


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT / "results" / "structure_smoothing"
    / "experiment-20261117T102719Z-1b827758b270"
)
DEFAULT_OUTPUT_ROOT = ROOT / "results" / "edge_comparison"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _within(base: Path, relative: str) -> Path:
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError(f"path escapes expected directory: {relative}")
    return path


def _read_u8(path: Path) -> tuple[np.ndarray, str]:
    with Image.open(path) as image:
        if image.mode not in ("L", "RGB"):
            raise ValueError(f"expected 8-bit L or RGB: {path} ({image.mode})")
        return np.array(image, dtype=np.uint8, copy=True), image.mode


def _gray(pixels: np.ndarray, mode: str) -> np.ndarray:
    """Use one 8-bit conversion on both originals and smoothed displays."""

    if mode == "L":
        return pixels.copy()
    if mode == "RGB":
        return cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
    raise ValueError(f"unsupported mode: {mode}")


def _detect(gray: np.ndarray, low: float, high: float, aperture: int, l2: bool) -> np.ndarray:
    if gray.dtype != np.uint8 or gray.ndim != 2:
        raise ValueError("Canny input must be 8-bit single-channel")
    return cv2.Canny(gray, low, high, apertureSize=aperture, L2gradient=l2)


def _settings(low: float, high: float, aperture: int, l2: bool) -> dict:
    if not (np.isfinite(low) and np.isfinite(high) and 0 <= low < high):
        raise ValueError("thresholds must be finite with 0 <= low < high")
    if aperture not in (3, 5, 7):
        raise ValueError("aperture must be 3, 5, or 7")
    return {
        "low_threshold": low,
        "high_threshold": high,
        "aperture_size": aperture,
        "l2_gradient": l2,
        "grayscale": "RGB: cv2.COLOR_RGB2GRAY on uint8 RGB; L: unchanged",
        "canny_input": "8-bit uint8 grayscale, range 0..255; no contrast stretch or extra blur",
        "smoothing_display": "saved output.png, clipped/rounded by prior smoothing workflow; float output.npy is untouched",
    }


def _load_grid(source: Path) -> dict[str, dict[tuple[float, float], dict]]:
    with (source / "runs.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = {(name, lam, kappa) for name in SOURCES for lam in LAMBDAS for kappa in KAPPAS}
    observed = [(row["image"], float(row["lambda"]), float(row["kappa"])) for row in rows]
    if len(rows) != len(expected) or set(observed) != expected:
        raise ValueError("smoothing CSV lacks the exact 18 combinations")
    grid = {name: {} for name in SOURCES}
    for row in rows:
        name, lam, kappa = row["image"], float(row["lambda"]), float(row["kappa"])
        record_path = _within(source, row["record"])
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if (record["parameters"]["lambda"], record["parameters"]["kappa"],
                record["parameters"]["beta_max"]) != (lam, kappa, 1e5):
            raise ValueError(f"smoothing record parameter mismatch: {record_path}")
        input_path = (ROOT / row["input"]).resolve()
        if not input_path.is_relative_to(ROOT) or _sha256_file(input_path) != record["input"]["file_sha256"]:
            raise ValueError(f"smoothing input differs from saved record: {record_path}")
        display_path = _within(source, row["display_result"])
        if display_path != _within(record_path.parent, record["output"]["display"]):
            raise ValueError(f"display path mismatch: {record_path}")
        display, mode = _read_u8(display_path)
        raw = np.load(_within(source, row["float_result"]), allow_pickle=False)
        expected_display = np.rint(np.clip(raw, 0.0, 1.0) * 255).astype(np.uint8)
        if (mode != record["input"]["mode"] or raw.dtype != np.float64
                or not np.array_equal(display, expected_display)):
            raise ValueError(f"display PNG differs from saved float result: {record_path}")
        grid[name][(lam, kappa)] = {
            "display": display_path,
            "smoothing_record": record_path,
            "input": input_path,
        }
    return grid


def _roi(source: Path, name: str) -> tuple[int, int, int, int]:
    data = json.loads((source / name / "roi.json").read_text(encoding="utf-8"))
    return tuple(data["xyxy"])


def _write_edge(
    image_path: Path, output_path: Path, name: str, kind: str,
    lam: float | None, kappa: float | None, settings: dict,
    smoothing_record: Path | None,
) -> tuple[dict, Image.Image]:
    pixels, mode = _read_u8(image_path)
    gray = _gray(pixels, mode)
    edges = _detect(
        gray, settings["low_threshold"], settings["high_threshold"],
        settings["aperture_size"], settings["l2_gradient"],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(edges, mode="L").save(output_path, format="PNG")
    row = {
        "image": name,
        "kind": kind,
        "lambda": "" if lam is None else lam,
        "kappa": "" if kappa is None else kappa,
        "source_image": str(image_path.relative_to(ROOT).as_posix()),
        "smoothing_record": "" if smoothing_record is None else str(smoothing_record.relative_to(ROOT).as_posix()),
        "source_sha256": _sha256_file(image_path),
        "source_mode": mode,
        "width": gray.shape[1],
        "height": gray.shape[0],
        "gray_min": int(gray.min()),
        "gray_max": int(gray.max()),
        "grayscale_sha256": _sha256_bytes(gray.tobytes()),
        "low_threshold": settings["low_threshold"],
        "high_threshold": settings["high_threshold"],
        "aperture_size": settings["aperture_size"],
        "l2_gradient": settings["l2_gradient"],
        "edge_pixels": int(np.count_nonzero(edges)),
        "edge_sha256": _sha256_bytes(edges.tobytes()),
        "edge_path": str(output_path.relative_to(ROOT).as_posix()),
    }
    return row, Image.fromarray(edges)


def run(source: Path, output_root: Path, low: float, high: float, aperture: int, l2: bool) -> Path:
    source = source.resolve()
    output_root = output_root.resolve()
    if not source.is_relative_to(ROOT) or not output_root.is_relative_to(ROOT):
        raise ValueError("source and output directories must be inside the repository")
    settings = _settings(low, high, aperture, l2)
    grid = _load_grid(source)
    output_root.mkdir(parents=True, exist_ok=True)
    output = output_root / f"edges-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:12]}"
    output.mkdir()
    rows = []
    for name in SOURCES:
        folder = output / name
        input_path = next(iter(grid[name].values()))["input"]
        original_row, original_edges = _write_edge(
            input_path, folder / "input_edges.png", name, "input", None, None, settings, None
        )
        rows.append(original_row)
        images = {"input": original_edges}
        for kappa in KAPPAS:
            for lam in LAMBDAS:
                item = grid[name][(lam, kappa)]
                label = f"lambda-{lam:g}_kappa-{kappa:g}"
                row, edge_image = _write_edge(
                    item["display"], folder / f"{label}_edges.png", name, "smoothed",
                    lam, kappa, settings, item["smoothing_record"],
                )
                rows.append(row)
                images[(lam, kappa)] = edge_image
                print(f"{name} {label}: {row['edge_pixels']} edge pixels")
        roi = _roi(source, name)
        _panel(images, roi, zoom=False).save(folder / "full_edge_comparison.png")
        _panel(images, roi, zoom=True).save(folder / "same_region_edge_zoom.png")
        (folder / "roi.json").write_text(json.dumps({"xyxy": roi}, indent=2) + "\n", encoding="utf-8")
    with (output / "edges.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_experiment": str(source.relative_to(ROOT).as_posix()),
        "settings": settings,
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pillow": PIL.__version__,
            "opencv_python_headless": importlib.metadata.version("opencv-python-headless"),
            "cv2": cv2.__version__,
        },
        "row_count": len(rows),
        "panel_layout": "input duplicated in each kappa row; columns are input and the three lambda values",
        "roi": "same saved pixel ROI as the smoothing comparison; nearest-neighbor enlargement",
    }
    (output / "edge_experiment.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(output.resolve())
    return output


def check(output: Path) -> Path:
    """Recompute all 21 maps and verify each per-image parameter pairing."""

    output = output.resolve()
    record = json.loads((output / "edge_experiment.json").read_text(encoding="utf-8"))
    settings = record["settings"]
    _settings(settings["low_threshold"], settings["high_threshold"],
              settings["aperture_size"], settings["l2_gradient"])
    with (output / "edges.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 21 or record["row_count"] != 21:
        raise ValueError("expected three inputs and 18 smoothed edge maps")
    grouped = {name: [] for name in SOURCES}
    for row in rows:
        grouped[row["image"]].append(row)
        row_settings = (
            float(row["low_threshold"]), float(row["high_threshold"]),
            int(row["aperture_size"]), row["l2_gradient"] == "True",
        )
        if row_settings != (
            settings["low_threshold"], settings["high_threshold"],
            settings["aperture_size"], settings["l2_gradient"],
        ):
            raise ValueError(f"paired Canny settings differ: {row['image']}")
        source_path = _within(ROOT, row["source_image"])
        if _sha256_file(source_path) != row["source_sha256"]:
            raise ValueError(f"source image changed: {source_path}")
        pixels, mode = _read_u8(source_path)
        gray = _gray(pixels, mode)
        recalculated = _detect(gray, *row_settings)
        edge_path = _within(ROOT, row["edge_path"])
        stored, stored_mode = _read_u8(edge_path)
        if (stored_mode != "L" or mode != row["source_mode"]
                or gray.shape != (int(row["height"]), int(row["width"]))
                or int(gray.min()) != int(row["gray_min"])
                or int(gray.max()) != int(row["gray_max"])
                or _sha256_bytes(gray.tobytes()) != row["grayscale_sha256"]
                or _sha256_bytes(recalculated.tobytes()) != row["edge_sha256"]
                or int(np.count_nonzero(recalculated)) != int(row["edge_pixels"])
                or not np.array_equal(stored, recalculated)):
            raise ValueError(f"saved edge pixels do not reproduce: {edge_path}")
    for name, group in grouped.items():
        combinations = {(float(row["lambda"]), float(row["kappa"])) for row in group if row["kind"] == "smoothed"}
        if len(group) != 7 or sum(row["kind"] == "input" for row in group) != 1 or combinations != {
            (lam, kappa) for lam in LAMBDAS for kappa in KAPPAS
        }:
            raise ValueError(f"input/output pairing is incomplete: {name}")
    checks = output / f"checks-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:12]}"
    checks.mkdir()
    summary_path = checks / "checks.json"
    summary_path.write_text(json.dumps({
        "actor": "智能体执行验证",
        "paired_settings_equal": True,
        "reproduced_edge_maps": len(rows),
        "pixel_comparison": "decoded uint8 pixels exactly equal after recomputation",
        "source_bytes_equal": True,
        "passed": True,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(summary_path.resolve())
    return summary_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run", "check"))
    parser.add_argument("edge_experiment", nargs="?", type=Path)
    parser.add_argument("--source-experiment", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--low", type=float, default=60)
    parser.add_argument("--high", type=float, default=120)
    parser.add_argument("--aperture", type=int, default=3)
    parser.add_argument("--l2", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    if args.command == "run":
        run(args.source_experiment, args.output_root, args.low, args.high, args.aperture, args.l2)
    elif args.edge_experiment is None:
        parser.error("check requires an edge experiment directory")
    else:
        check(args.edge_experiment)


if __name__ == "__main__":
    main()
