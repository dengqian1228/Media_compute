"""Prepare the archived inputs and run the fixed L0 parameter comparison.

Run from the repository root. The original image downloads are kept in
data/structure_smoothing/sources; this program never downloads replacements.
"""

import argparse
import csv
import hashlib
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from l0_smoothing.workflow import replay_record, run_and_save


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "structure_smoothing"
MAX_SIDE = 512
LAMBDAS = (0.005, 0.02, 0.08)
KAPPAS = (1.5, 2.0)
BETA_MAX = 1e5

SOURCES = {
    "beach": {
        "filename": "beach.png",
        "sha256": "9c03c82a6f28dd71e8d68339e82512eaaeaa183e1afa96e28ea4da5de5fd9312",
        "mode": "RGB",
        "source_page": "https://jiaya.me/file/archive/projects/L0smoothing/ImageSmoothing.htm",
        "download_url": "https://jiaya.me/file/archive/projects/L0smoothing/results/Smoothing/beach/beach.png",
        "author": "未在官网页面注明",
        "license": "未在官网页面注明；公开再分发前须核实授权",
        "roi": (0.31, 0.30, 0.56, 0.63),
    },
    "brick_window_gray": {
        "filename": "Brick_wall_and_window.jpg",
        "sha256": "4f9cb1f35b75bc8309cc31c2e05f12772e7df0a602ddec05058e47e6d300de91",
        "mode": "L",
        "source_page": "https://commons.wikimedia.org/wiki/File:Brick_wall_and_window.jpg",
        "download_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Brick_wall_and_window.jpg",
        "author": "Tarasna0922",
        "license": "CC BY-SA 4.0; derived grayscale and smoothed images retain this license",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "roi": (0.32, 0.28, 0.57, 0.61),
    },
    "sunflower": {
        "filename": "Sunflower_in_a_field.jpg",
        "sha256": "8782a4e489f826be45c20574fd94aa3a7c7632ed71fc4d07388916dcb8be4100",
        "mode": "RGB",
        "source_page": "https://commons.wikimedia.org/wiki/File:Sunflower_in_a_field.jpg",
        "download_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Sunflower_in_a_field.jpg",
        "author": "Timovn",
        "license": "CC BY 4.0; resize/smoothing changes are noted",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "roi": (0.45, 0.46, 0.70, 0.79),
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prepare() -> None:
    """Verify archived originals and make deterministic 8-bit L/RGB PNG inputs."""

    output = DATA / "inputs"
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"max_side": MAX_SIDE, "resampling": "Pillow LANCZOS", "images": {}}
    for name, spec in SOURCES.items():
        source = DATA / "sources" / spec["filename"]
        original = source.read_bytes()
        if sha256(original) != spec["sha256"]:
            raise ValueError(f"source SHA-256 mismatch: {source}")
        with Image.open(source) as image:
            original_mode, original_size = image.mode, image.size
            # The photo orientation is applied before conversion and resizing.
            processed = ImageOps.exif_transpose(image).convert(spec["mode"])
            processed.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            final_size = processed.size
            stream = io.BytesIO()
            processed.save(stream, format="PNG")
            encoded = stream.getvalue()
        target = output / f"{name}.png"
        if target.exists():
            if target.read_bytes() != encoded:
                raise FileExistsError(f"existing preprocessed input differs: {target}")
        else:
            target.write_bytes(encoded)
        manifest["images"][name] = {
            **{key: value for key, value in spec.items() if key != "roi"},
            "source_size": list(original_size),
            "source_mode": original_mode,
            "input_file": str(target.relative_to(ROOT).as_posix()),
            "input_size": list(final_size),
            "input_mode": spec["mode"],
            "input_sha256": sha256(encoded),
            "preprocessing": [
                "Apply EXIF orientation if present",
                f"convert to 8-bit {spec['mode']} with Pillow",
                f"resize within {MAX_SIDE}x{MAX_SIDE}, preserving aspect ratio, LANCZOS",
                "save as PNG; no crop or contrast adjustment",
            ],
            "roi_fraction_xyxy": list(spec["roi"]),
        }
        print(f"{name}: {original_size} {original_mode} -> {final_size} {spec['mode']}")
    manifest_path = DATA / "manifest.json"
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if manifest_path.exists():
        if manifest_path.read_text(encoding="utf-8") != manifest_text:
            raise FileExistsError(f"existing manifest differs: {manifest_path}")
    else:
        manifest_path.write_text(manifest_text, encoding="utf-8")


def _panel(images: dict[tuple[float, float] | str, Image.Image], roi: tuple[int, ...], zoom: bool) -> Image.Image:
    source = images["input"]
    width, height = source.size
    if zoom:
        x0, y0, x1, y1 = roi
        crop_width, crop_height = x1 - x0, y1 - y0
        scale = max(2, min(4, width // crop_width))
        width, height = crop_width * scale, crop_height * scale
    margin, label_height = 10, 26
    panel = Image.new("RGB", (4 * (width + margin) + margin, 2 * (height + label_height + margin) + margin), "white")
    draw = ImageDraw.Draw(panel)
    font = ImageFont.load_default()
    for row, kappa in enumerate(KAPPAS):
        for col in range(4):
            key = "input" if col == 0 else (LAMBDAS[col - 1], kappa)
            image = images[key].convert("RGB")
            if zoom:
                image = image.crop(roi).resize((width, height), Image.Resampling.NEAREST)
            label = "input" if col == 0 else f"lambda={LAMBDAS[col - 1]:g}, kappa={kappa:g}"
            left = margin + col * (width + margin)
            top = margin + row * (height + label_height + margin)
            draw.text((left, top + 5), label, fill="black", font=font)
            panel.paste(image, (left, top + label_height))
            if not zoom and col == 0:
                draw.rectangle(tuple((left + roi[i], top + label_height + roi[i+1]) for i in (0, 2)), outline="red", width=2)
    return panel


def _roi_pixels(size: tuple[int, int], fractions: tuple[float, ...]) -> tuple[int, int, int, int]:
    width, height = size
    return (round(fractions[0] * width), round(fractions[1] * height),
            round(fractions[2] * width), round(fractions[3] * height))


def run(output_root: Path) -> Path:
    """Run all 18 cases once, preserving every run's existing save format."""

    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    for name in SOURCES:
        path = DATA / "inputs" / f"{name}.png"
        if sha256(path.read_bytes()) != manifest["images"][name]["input_sha256"]:
            raise ValueError(f"prepared input differs from the manifest: {name}")
    output_root.mkdir(parents=True, exist_ok=True)
    experiment = output_root / f"experiment-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:12]}"
    experiment.mkdir()
    rows = []
    for name, spec in SOURCES.items():
        source = DATA / "inputs" / f"{name}.png"
        folder = experiment / name
        folder.mkdir()
        with Image.open(source) as image:
            images = {"input": image.copy()}
            input_float = np.asarray(image, dtype=np.float64) / 255.0
        roi = _roi_pixels(images["input"].size, spec["roi"])
        for kappa in KAPPAS:
            for lam in LAMBDAS:
                record_path = run_and_save(source, folder, lambda_=lam, kappa=kappa, beta_max=BETA_MAX)
                record = json.loads(record_path.read_text(encoding="utf-8"))
                display_path = record_path.parent / record["output"]["display"]
                float_path = record_path.parent / record["output"]["float"]
                mean_abs_change = float(np.mean(np.abs(np.load(float_path, allow_pickle=False) - input_float)))
                with Image.open(display_path) as image:
                    images[(lam, kappa)] = image.copy()
                row = {
                    "image": name,
                    "input": str(source.relative_to(ROOT).as_posix()),
                    "lambda": lam,
                    "kappa": kappa,
                    "beta_max": BETA_MAX,
                    "iterations": record["iterations"],
                    "elapsed_seconds": record["elapsed_seconds"],
                    "mean_abs_change": mean_abs_change,
                    "record": str(record_path.relative_to(experiment).as_posix()),
                    "float_result": str(float_path.relative_to(experiment).as_posix()),
                    "display_result": str(display_path.relative_to(experiment).as_posix()),
                }
                rows.append(row)
                print(f"{name} lambda={lam:g} kappa={kappa:g}: {row['iterations']} iterations, {row['elapsed_seconds']:.3f}s")
        _panel(images, roi, zoom=False).save(folder / "full_comparison.png")
        _panel(images, roi, zoom=True).save(folder / "same_region_zoom.png")
        (folder / "roi.json").write_text(json.dumps({"xyxy": roi, "fraction_xyxy": spec["roi"]}, indent=2) + "\n", encoding="utf-8")
    with (experiment / "runs.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (experiment / "experiment.json").write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {"lambdas": LAMBDAS, "kappas": KAPPAS, "beta_max": BETA_MAX},
        "source_manifest": str((DATA / "manifest.json").relative_to(ROOT).as_posix()),
        "row_count": len(rows),
        "zoom": "same ROI in all eight tiles, nearest-neighbor enlargement; full panel marks ROI on input",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(experiment.resolve())
    return experiment


def check(experiment: Path) -> Path:
    """Audit the saved grid and replay three different images and settings."""

    experiment = experiment.resolve()
    with (experiment / "runs.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = {(name, lam, kappa) for name in SOURCES for lam in LAMBDAS for kappa in KAPPAS}
    observed = {(row["image"], float(row["lambda"]), float(row["kappa"])) for row in rows}
    if len(rows) != len(expected) or observed != expected:
        raise ValueError("CSV grid has missing or duplicate combinations")
    for row in rows:
        record_path = (experiment / row["record"]).resolve()
        if not record_path.is_relative_to(experiment):
            raise ValueError("record path escapes experiment")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        params = record["parameters"]
        if (params["lambda"], params["kappa"], params["beta_max"]) != (
            float(row["lambda"]), float(row["kappa"]), BETA_MAX
        ):
            raise ValueError(f"parameters differ: {record_path}")
        if record["iterations"] != int(row["iterations"]) or record["elapsed_seconds"] != float(row["elapsed_seconds"]):
            raise ValueError(f"run metrics differ: {record_path}")
        input_path = record_path.parent / record["input"]["copy"]
        if sha256(input_path.read_bytes()) != record["input"]["file_sha256"]:
            raise ValueError(f"saved input hash differs: {record_path}")
        float_path = (experiment / row["float_result"]).resolve()
        display_path = (experiment / row["display_result"]).resolve()
        if not float_path.is_relative_to(experiment) or not display_path.is_relative_to(experiment):
            raise ValueError("output path escapes experiment")
        floats = np.load(float_path, allow_pickle=False)
        with Image.open(display_path) as image:
            mode, size = image.mode, image.size
        with Image.open(input_path) as image:
            original = np.asarray(image, dtype=np.float64) / 255.0
        if floats.dtype != np.float64 or list(floats.shape) != record["output"]["shape"] or not np.isfinite(floats).all():
            raise ValueError(f"float artifact invalid: {record_path}")
        if mode != record["input"]["mode"] or size != (floats.shape[1], floats.shape[0]):
            raise ValueError(f"display artifact invalid: {record_path}")
        if abs(float(np.mean(np.abs(floats - original))) - float(row["mean_abs_change"])) > 1e-12:
            raise ValueError(f"mean absolute change differs: {record_path}")
    selected = {
        "beach": (0.005, 1.5),
        "brick_window_gray": (0.02, 2.0),
        "sunflower": (0.08, 1.5),
    }
    checks = experiment / f"checks-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:12]}"
    checks.mkdir()
    replays = []
    for row in rows:
        if selected.get(row["image"]) == (float(row["lambda"]), float(row["kappa"])):
            replay_path, passed = replay_record(experiment / row["record"], checks)
            comparison = json.loads(replay_path.read_text(encoding="utf-8"))["comparison"]
            replays.append({"image": row["image"], "lambda": float(row["lambda"]),
                            "kappa": float(row["kappa"]), "replay_record": str(replay_path.relative_to(experiment).as_posix()),
                            "passed": passed, "max_float_abs_error": comparison["max_float_abs_error"],
                            "different_pixel_count": comparison["different_pixel_count"]})
    summary = {"actor": "智能体执行验证", "audited_rows": len(rows), "grid_complete": True,
               "artifact_checks": "input SHA-256, parameters, iterations, elapsed, mean absolute change, float dtype/shape/finite, display mode/shape",
               "replays": replays, "passed": len(replays) == 3 and all(row["passed"] for row in replays)}
    summary_path = checks / "checks.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(summary_path.resolve())
    if not summary["passed"]:
        raise ValueError("a replay comparison failed")
    return summary_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run", "check"))
    parser.add_argument("experiment", nargs="?", type=Path)
    parser.add_argument("--output-root", type=Path, default=ROOT / "results" / "structure_smoothing")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "run":
        run(args.output_root)
    elif args.experiment is None:
        parser.error("check needs an experiment directory")
    else:
        check(args.experiment)


if __name__ == "__main__":
    main()
