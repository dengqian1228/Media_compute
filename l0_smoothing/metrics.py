"""Full-reference metrics for saved 8-bit L/RGB experiment images.

PSNR uses the mean squared error over all pixels and channels, data range 255.
SSIM uses the single-scale Wang et al. formula with an 11x11 normalized Gaussian
window (sigma=1.5), population moments, K1=.01, K2=.03, and only window centres
whose full window lies inside the image. RGB SSIM averages channel scores; it
does not convert to luminance or downsample. This convention is explicit because
SSIM implementations with different channel/scale/border choices need not agree.

Formula reference: https://www.cns.nyu.edu/~lcv/ssim/
"""

import cv2
import numpy as np


METRIC_SPEC = {
    "input": "decoded uint8 L or RGB pixels; saved display PNG for recovery",
    "data_range": 255,
    "psnr": "10*log10(255**2 / mean((reference-candidate)**2)); all channels",
    "ssim": "single-scale; 11x11 Gaussian sigma=1.5; population moments",
    "ssim_k1": 0.01,
    "ssim_k2": 0.03,
    "ssim_border": "valid only; discard 5 pixels on every side",
    "ssim_channels": "arithmetic mean of per-channel scores for RGB",
    "ssim_scale": "no downsampling; no luminance conversion",
    "reference": "https://www.cns.nyu.edu/~lcv/ssim/",
}


def _validate(reference: np.ndarray, candidate: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a, b = np.asarray(reference), np.asarray(candidate)
    if a.dtype != np.uint8 or b.dtype != np.uint8:
        raise TypeError("metrics require uint8 pixels (data_range=255)")
    if a.shape != b.shape:
        raise ValueError("reference and candidate must have the same shape")
    if a.ndim not in (2, 3) or (a.ndim == 3 and a.shape[2] != 3):
        raise ValueError("metrics require shape (H, W) or (H, W, 3)")
    if not a.shape[0] or not a.shape[1]:
        raise ValueError("image dimensions must be nonzero")
    return a.astype(np.float64), b.astype(np.float64)


def _psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = float(np.mean((a - b) ** 2))
    return float("inf") if mse == 0.0 else float(10.0 * np.log10(255.0 ** 2 / mse))


def _ssim(a: np.ndarray, b: np.ndarray) -> float:
    if min(a.shape[:2]) < 11:
        raise ValueError("SSIM requires height and width >= 11")

    def average(x):
        # Border values never contribute: discard radius 5 after filtering.
        return cv2.GaussianBlur(x, (11, 11), 1.5, sigmaY=1.5)[5:-5, 5:-5]

    mu_a, mu_b = average(a), average(b)
    var_a = average(a * a) - mu_a * mu_a
    var_b = average(b * b) - mu_b * mu_b
    covariance = average(a * b) - mu_a * mu_b
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    local = ((2 * mu_a * mu_b + c1) * (2 * covariance + c2)) / (
        (mu_a * mu_a + mu_b * mu_b + c1) * (var_a + var_b + c2)
    )
    # Equal image dimensions give equal numbers of centres for every channel,
    # so this is also the arithmetic mean of the three per-channel means.
    return float(np.mean(local))


def psnr(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Return PSNR in dB; identical images return positive infinity."""
    return _psnr(*_validate(reference, candidate))


def ssim(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Return single-scale valid-window SSIM with the convention above."""
    return _ssim(*_validate(reference, candidate))


def image_metrics(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    """Compute both metrics against the same clean uint8 reference."""
    a, b = _validate(reference, candidate)
    return {"psnr_db": _psnr(a, b), "ssim": _ssim(a, b)}
