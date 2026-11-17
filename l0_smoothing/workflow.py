"""Eight-bit image I/O, saved runs, and pixel-based replay for ``smooth_l0``."""

import hashlib
import json
import platform
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import PIL
from PIL import Image

from .core import smooth_l0


RECORD_VERSION = 1
DEFAULT_FLOAT_ATOL = 1e-12


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_pixels(pixels: np.ndarray, mode: str) -> str:
    """Identify decoded pixels, including their shape and channel meaning."""

    digest = hashlib.sha256()
    digest.update(mode.encode("ascii"))
    digest.update(json.dumps(list(pixels.shape)).encode("ascii"))
    digest.update(np.ascontiguousarray(pixels).tobytes())
    return digest.hexdigest()


def read_8bit_image(path: str | Path) -> tuple[np.ndarray, np.ndarray, str]:
    """Return a float64 [0, 1] array, its uint8 pixels, and mode L or RGB."""

    with Image.open(path) as image:
        if image.mode not in ("L", "RGB"):
            raise ValueError(f"expected an 8-bit L or RGB image, got mode {image.mode}")
        pixels = np.array(image, dtype=np.uint8, copy=True)
        mode = image.mode
    return pixels.astype(np.float64) / 255.0, pixels, mode


def _display_pixels(image: np.ndarray) -> np.ndarray:
    """Clip and round only the display copy; the float result stays unchanged."""

    return np.rint(np.clip(image, 0.0, 1.0) * 255.0).astype(np.uint8)


def _environment() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pillow": PIL.__version__,
        "platform": platform.platform(),
    }


def _new_run_directory(parent: Path, prefix: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        directory = parent / f"{prefix}-{stamp}-{uuid.uuid4().hex[:12]}"
        try:
            directory.mkdir()
            return directory
        except FileExistsError:
            continue
    raise FileExistsError("could not create a unique run directory")


def _artifact_path(record_directory: Path, relative: str) -> Path:
    """Keep paths from a JSON record inside that record's directory."""

    path = (record_directory / relative).resolve()
    if not path.is_relative_to(record_directory.resolve()):
        raise ValueError(f"artifact path escapes record directory: {relative}")
    return path


def _save_run(
    source_path: Path,
    output_parent: Path,
    prefix: str,
    mode: str,
    input_pixels: np.ndarray,
    result,
    comparison: dict | None = None,
) -> Path:
    directory = _new_run_directory(output_parent, prefix)
    input_name = f"input{source_path.suffix.lower()}"
    input_copy = directory / input_name
    shutil.copyfile(source_path, input_copy)
    _, copied_pixels, copied_mode = read_8bit_image(input_copy)
    if copied_mode != mode or not np.array_equal(copied_pixels, input_pixels):
        raise ValueError("input pixels changed while the run was being saved")

    float_name = "output.npy"
    display_name = "output.png"
    np.save(directory / float_name, result.image, allow_pickle=False)
    display = _display_pixels(result.image)
    display_image = Image.fromarray(display)
    if display_image.mode != mode:
        raise ValueError("display mode does not match input mode")
    display_image.save(directory / display_name, format="PNG")

    record = {
        "record_version": RECORD_VERSION,
        "kind": prefix,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "source_path": str(source_path.resolve()),
            "copy": input_name,
            "file_sha256": _sha256_file(input_copy),
            "pixel_sha256": _sha256_pixels(input_pixels, mode),
            "mode": mode,
            "shape": list(input_pixels.shape),
        },
        "output": {
            "float": float_name,
            "display": display_name,
            "shape": list(result.image.shape),
            "dtype": str(result.image.dtype),
            "display_pixel_sha256": _sha256_pixels(display, mode),
        },
        "parameters": result.parameters,
        "iterations": result.iterations,
        "elapsed_seconds": result.elapsed_seconds,
        "environment": _environment(),
    }
    if comparison is not None:
        record["comparison"] = comparison
    record_path = directory / "run.json"
    record_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record_path


def run_and_save(
    input_path: str | Path,
    output_parent: str | Path,
    lambda_: float = 0.02,
    kappa: float = 2.0,
    beta_max: float = 1e5,
) -> Path:
    """Run the existing core and save an untouched input copy and both outputs."""

    source = Path(input_path)
    normalized, pixels, mode = read_8bit_image(source)
    result = smooth_l0(normalized, lambda_=lambda_, kappa=kappa, beta_max=beta_max)
    return _save_run(source, Path(output_parent), "run", mode, pixels, result)


def replay_record(
    record_path: str | Path,
    output_parent: str | Path | None = None,
    input_path: str | Path | None = None,
    float_atol: float = DEFAULT_FLOAT_ATOL,
) -> tuple[Path, bool]:
    """Rerun from a record; compare decoded input/output pixels and float values.

    A different PNG byte stream with identical decoded pixels is accepted.
    A new directory stores every completed replay, including failed output
    comparisons. An input pixel mismatch stops before the algorithm runs.
    """

    if not np.isfinite(float_atol) or float_atol < 0:
        raise ValueError("float_atol must be finite and nonnegative")
    reference_path = Path(record_path).resolve()
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    if reference.get("record_version") != RECORD_VERSION:
        raise ValueError("unsupported record version")
    reference_directory = reference_path.parent
    original_input = _artifact_path(reference_directory, reference["input"]["copy"])
    selected_input = Path(input_path) if input_path is not None else original_input
    normalized, pixels, mode = read_8bit_image(selected_input)
    pixels_match = (
        mode == reference["input"]["mode"]
        and list(pixels.shape) == reference["input"]["shape"]
        and _sha256_pixels(pixels, mode) == reference["input"]["pixel_sha256"]
    )
    if not pixels_match:
        raise ValueError("input decoded pixels differ from the recorded input")

    parameters = reference["parameters"]
    result = smooth_l0(
        normalized,
        lambda_=parameters["lambda"],
        kappa=parameters["kappa"],
        beta_max=parameters["beta_max"],
    )
    original_float = np.load(
        _artifact_path(reference_directory, reference["output"]["float"]),
        allow_pickle=False,
    )
    if original_float.shape != result.image.shape or original_float.dtype != np.float64:
        raise ValueError("recorded float output has a different shape or dtype")
    if not np.all(np.isfinite(original_float)):
        raise ValueError("recorded float output contains non-finite values")
    original_display_path = _artifact_path(
        reference_directory, reference["output"]["display"]
    )
    _, original_display, original_mode = read_8bit_image(original_display_path)
    display = _display_pixels(result.image)
    if original_mode != mode or original_display.shape != display.shape:
        raise ValueError("recorded display output has a different mode or shape")

    error = np.abs(result.image - original_float)
    max_float_error = float(np.max(error))
    pixel_delta = np.abs(display.astype(np.int16) - original_display.astype(np.int16))
    different_pixels = np.any(pixel_delta != 0, axis=2) if mode == "RGB" else pixel_delta != 0
    different_pixel_count = int(np.count_nonzero(different_pixels))
    passed = max_float_error <= float_atol and different_pixel_count == 0
    current_environment = _environment()
    comparison = {
        "reference_record": str(reference_path),
        "input_decoded_pixels_equal": True,
        "input_file_bytes_equal": _sha256_file(selected_input)
        == reference["input"]["file_sha256"],
        "float_atol": float_atol,
        "max_float_abs_error": max_float_error,
        "mean_float_abs_error": float(np.mean(error)),
        "float_within_tolerance": max_float_error <= float_atol,
        "different_pixel_count": different_pixel_count,
        "max_pixel_channel_error": int(np.max(pixel_delta)),
        "display_pixels_equal": different_pixel_count == 0,
        "environment_versions_equal": {
            name: current_environment[name] == reference["environment"][name]
            for name in ("python", "numpy", "pillow")
        },
        "passed": passed,
    }
    parent = Path(output_parent) if output_parent is not None else reference_directory.parent
    new_record = _save_run(
        selected_input, parent, "replay", mode, pixels, result, comparison
    )
    return new_record, passed
