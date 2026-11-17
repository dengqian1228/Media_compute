"""Independent small checks of metric scale, channels and SSIM windows."""

import unittest

import numpy as np

from l0_smoothing.metrics import image_metrics, psnr, ssim


class MetricTests(unittest.TestCase):
    def test_constant_difference_has_known_psnr_and_ssim(self):
        a = np.full((19, 23), 100, dtype=np.uint8)
        b = np.full_like(a, 110)
        result = image_metrics(a, b)
        self.assertAlmostEqual(result["psnr_db"], 10 * np.log10(255 ** 2 / 100), places=12)
        c1 = (0.01 * 255) ** 2
        self.assertAlmostEqual(result["ssim"], (2 * 100 * 110 + c1) / (100**2 + 110**2 + c1), places=11)

    def test_identical_images_and_rgb_channel_average(self):
        rng = np.random.default_rng(2023010721)
        a = rng.integers(0, 256, (15, 17, 3), dtype=np.uint8)
        b = a.copy()
        b[:, :, 1] = 255 - a[:, :, 1]
        self.assertTrue(np.isposinf(psnr(a, a)))
        self.assertAlmostEqual(ssim(a, a), 1.0, places=12)
        expected = np.mean([ssim(a[:, :, c], b[:, :, c]) for c in range(3)])
        self.assertAlmostEqual(ssim(a, b), expected, places=12)

    def test_ssim_matches_direct_valid_window_weighted_moments(self):
        # This reference uses explicit Gaussian weights and every valid patch,
        # without OpenCV or the implementation's filtered moments.
        rng = np.random.default_rng(31)
        a = rng.integers(0, 256, (13, 15), dtype=np.uint8)
        b = rng.integers(0, 256, (13, 15), dtype=np.uint8)
        axis = np.arange(-5, 6, dtype=np.float64)
        weights = np.exp(-(axis[:, None] ** 2 + axis[None, :] ** 2) / (2 * 1.5**2))
        weights /= weights.sum()
        c1, c2 = (0.01 * 255)**2, (0.03 * 255)**2
        scores = []
        for y in range(a.shape[0] - 10):
            for x in range(a.shape[1] - 10):
                aa, bb = a[y:y+11, x:x+11].astype(float), b[y:y+11, x:x+11].astype(float)
                ma, mb = np.sum(weights * aa), np.sum(weights * bb)
                va = np.sum(weights * (aa - ma)**2)
                vb = np.sum(weights * (bb - mb)**2)
                cov = np.sum(weights * (aa - ma) * (bb - mb))
                scores.append((2*ma*mb+c1)*(2*cov+c2)/((ma*ma+mb*mb+c1)*(va+vb+c2)))
        self.assertAlmostEqual(ssim(a, b), np.mean(scores), places=12)

    def test_invalid_dtype_shape_and_window_are_rejected(self):
        a = np.zeros((11, 11), dtype=np.uint8)
        with self.assertRaises(TypeError):
            image_metrics(a.astype(float), a)
        with self.assertRaises(ValueError):
            image_metrics(a, np.zeros((12, 11), dtype=np.uint8))
        with self.assertRaises(ValueError):
            image_metrics(np.zeros((11, 11, 4), dtype=np.uint8), np.zeros((11, 11, 4), dtype=np.uint8))
        with self.assertRaises(ValueError):
            ssim(a[:10], a[:10])
        # PSNR has no sliding-window restriction and remains defined here.
        self.assertEqual(psnr(np.zeros((1, 1), dtype=np.uint8), np.full((1, 1), 255, dtype=np.uint8)), 0)


if __name__ == "__main__":
    unittest.main()
