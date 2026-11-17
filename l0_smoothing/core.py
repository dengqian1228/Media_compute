"""Periodic L0 gradient smoothing described by the project members.

Arrays use (height, width) for grayscale and (height, width, 3) for RGB.
Axis 1 is x, and axis 0 is y. Image loading and saving are outside this module.
"""

from dataclasses import dataclass
from numbers import Real
from time import perf_counter

import numpy as np


@dataclass(frozen=True)
class L0SmoothingResult:
    """Result array, effective parameters, number of iterations, and elapsed time."""

    image: np.ndarray
    parameters: dict[str, float]
    iterations: int
    elapsed_seconds: float


def _positive_finite(value: Real, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not np.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return number


def _periodic_forward_differences(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Dx S = S[y, x+1] - S[y, x]; Dy S = S[y+1, x] - S[y, x]."""

    gx = np.roll(image, -1, axis=1) - image
    gy = np.roll(image, -1, axis=0) - image
    return gx, gy


def _threshold_gradients(
    gx: np.ndarray, gy: np.ndarray, lambda_: float, beta: float
) -> tuple[np.ndarray, np.ndarray]:
    """Set both directions and all channels to zero where q <= lambda / beta."""

    q = np.sum(gx * gx + gy * gy, axis=2, keepdims=True)
    keep = q > lambda_ / beta
    h = np.where(keep, gx, 0.0)
    v = np.where(keep, gy, 0.0)
    return h, v


def _frequency_responses(height: int, width: int) -> tuple[np.ndarray, np.ndarray]:
    """FFT symbols of periodic forward differences under NumPy's FFT convention."""

    dx = np.exp(2j * np.pi * np.fft.fftfreq(width))[None, :] - 1.0
    dy = np.exp(2j * np.pi * np.fft.fftfreq(height))[:, None] - 1.0
    return np.broadcast_to(dx, (height, width)), np.broadcast_to(dy, (height, width))


def _fft_update(
    input_fft: np.ndarray,
    h: np.ndarray,
    v: np.ndarray,
    beta: float,
    dx: np.ndarray,
    dy: np.ndarray,
) -> np.ndarray:
    """Solve the fixed-(h, v) quadratic subproblem, channel by channel."""

    # FFT(D* h) = conj(d) FFT(h); D* is the adjoint of forward difference.
    numerator = input_fft + beta * (
        np.conj(dx)[..., None] * np.fft.fft2(h, axes=(0, 1))
        + np.conj(dy)[..., None] * np.fft.fft2(v, axes=(0, 1))
    )
    denominator = 1.0 + beta * (np.abs(dx) ** 2 + np.abs(dy) ** 2)
    return np.fft.ifft2(numerator / denominator[..., None], axes=(0, 1)).real


def smooth_l0(
    image: np.ndarray,
    lambda_: float = 0.02,
    kappa: float = 2.0,
    beta_max: float = 1e5,
) -> L0SmoothingResult:
    """Minimize ||S-I||² + lambda*C(S) by the specified alternating updates.

    `image` must be a finite floating array in [0, 1], with shape (H, W)
    or (H, W, 3). The input is copied to float64 and never changed. Parameters
    must satisfy lambda > 0, kappa > 1, and beta_max > 2*lambda, so at least
    one iteration runs. An iteration uses its current beta, then multiplies
    beta by kappa; the loop ends once beta >= beta_max. No pixel clipping is
    applied, including after the final inverse FFT.
    """

    lambda_ = _positive_finite(lambda_, "lambda_")
    kappa = _positive_finite(kappa, "kappa")
    beta_max = _positive_finite(beta_max, "beta_max")
    if kappa <= 1:
        raise ValueError("kappa must be greater than 1")
    if 2 * lambda_ >= beta_max:
        raise ValueError("beta_max must be greater than 2 * lambda_")

    source = np.asarray(image)
    if source.ndim not in (2, 3) or (source.ndim == 3 and source.shape[2] != 3):
        raise ValueError("image must have shape (H, W) or (H, W, 3)")
    if source.shape[0] == 0 or source.shape[1] == 0:
        raise ValueError("image height and width must be nonzero")
    if not np.issubdtype(source.dtype, np.floating):
        raise TypeError("image must have a floating dtype")
    if not np.all(np.isfinite(source)) or np.any((source < 0) | (source > 1)):
        raise ValueError("image values must be finite and in [0, 1]")

    start = perf_counter()
    input_image = np.array(source, dtype=np.float64, copy=True)
    grayscale = input_image.ndim == 2
    if grayscale:
        input_image = input_image[..., None]

    # S = I; beta_0 = 2*lambda. The channel axis also covers grayscale (C=1).
    smoothed = input_image.copy()
    beta = 2.0 * lambda_
    iterations = 0
    height, width = input_image.shape[:2]
    dx, dy = _frequency_responses(height, width)
    input_fft = np.fft.fft2(input_image, axes=(0, 1))

    while beta < beta_max:
        # Auxiliary update: q_p = sum_c((Dx S)^2 + (Dy S)^2).
        gx, gy = _periodic_forward_differences(smoothed)
        h, v = _threshold_gradients(gx, gy, lambda_, beta)

        # Fixed-(h, v) FFT update for every channel, followed by real inverse.
        smoothed = _fft_update(input_fft, h, v, beta, dx, dy)
        iterations += 1
        beta *= kappa

    result = smoothed[..., 0] if grayscale else smoothed
    return L0SmoothingResult(
        image=result,
        parameters={"lambda": lambda_, "kappa": kappa, "beta_max": beta_max},
        iterations=iterations,
        elapsed_seconds=perf_counter() - start,
    )
