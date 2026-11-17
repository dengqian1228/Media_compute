"""Small deterministic checks of the in-memory L0 smoothing core."""

import unittest

import numpy as np

from l0_smoothing import smooth_l0
from l0_smoothing.core import (
    _fft_update,
    _frequency_responses,
    _periodic_forward_differences,
    _threshold_gradients,
)


class L0CoreTests(unittest.TestCase):
    def test_periodic_boundary_connects_last_row_and_column_to_first(self):
        image = np.array([[1.0, 2.0, 4.0], [8.0, 16.0, 32.0]])
        gx, gy = _periodic_forward_differences(image)
        np.testing.assert_array_equal(gx, [[1.0, 2.0, -3.0], [8.0, 16.0, -24.0]])
        np.testing.assert_array_equal(gy, [[7.0, 14.0, 28.0], [-7.0, -14.0, -28.0]])

    def test_color_threshold_is_joint_over_directions_and_channels(self):
        gx = np.array([[[0.5, 0.5, 0.0], [0.4, 0.4, 0.4]]])
        gy = np.array([[[0.0, 0.0, 0.0], [0.2, 0.2, 0.2]]])
        h, v = _threshold_gradients(gx, gy, lambda_=1.0, beta=2.0)
        np.testing.assert_array_equal(h[0, 0], [0.0, 0.0, 0.0])  # q = 0.5
        np.testing.assert_array_equal(v[0, 0], [0.0, 0.0, 0.0])
        np.testing.assert_array_equal(h[0, 1], gx[0, 1])  # q = 0.6
        np.testing.assert_array_equal(v[0, 1], gy[0, 1])

    def test_constant_grayscale_and_rgb_remain_constant_without_input_mutation(self):
        for image in (
            np.full((3, 4), 0.375, dtype=np.float32),
            np.broadcast_to([0.25, 0.5, 0.75], (3, 4, 3)).copy(),
        ):
            with self.subTest(shape=image.shape):
                before = image.copy()
                result = smooth_l0(image, beta_max=0.16)
                np.testing.assert_allclose(result.image, before, atol=1e-14, rtol=0)
                np.testing.assert_array_equal(image, before)
                self.assertFalse(np.shares_memory(result.image, image))
                self.assertEqual(result.image.dtype, np.float64)
                self.assertEqual(result.iterations, 2)  # beta: 0.04, 0.08
                self.assertEqual(
                    result.parameters,
                    {"lambda": 0.02, "kappa": 2.0, "beta_max": 0.16},
                )
                self.assertGreaterEqual(result.elapsed_seconds, 0.0)

    def test_non_square_rgb_input_keeps_shape_and_is_finite(self):
        image = np.array(
            [[[0.0, 0.2, 1.0], [0.8, 0.1, 0.3], [0.4, 0.6, 0.7]],
             [[0.9, 0.5, 0.1], [0.2, 0.7, 0.4], [1.0, 0.0, 0.5]]],
            dtype=np.float32,
        )
        before = image.copy()
        result = smooth_l0(image, beta_max=0.32)
        self.assertEqual(result.image.shape, image.shape)
        self.assertEqual(result.image.dtype, np.float64)
        self.assertTrue(np.all(np.isfinite(result.image)))
        np.testing.assert_array_equal(image, before)
        self.assertEqual(result.iterations, 3)

    def test_fft_update_matches_independently_built_linear_system(self):
        height, width = 2, 3
        input_image = np.array([[0.1, 0.7, 0.2], [0.9, 0.3, 0.5]])
        h = np.array([[0.2, -0.3, 0.1], [-0.2, 0.4, -0.1]])
        v = np.array([[0.3, -0.1, 0.2], [-0.3, 0.1, -0.2]])
        beta = 1.7

        # Build the forward-difference matrices directly by pixel indices.
        # This reference uses np.linalg.solve, not the implementation's FFT.
        size = height * width
        difference_x = np.zeros((size, size))
        difference_y = np.zeros((size, size))
        for row in range(height):
            for column in range(width):
                position = row * width + column
                difference_x[position, position] -= 1.0
                difference_x[position, row * width + (column + 1) % width] += 1.0
                difference_y[position, position] -= 1.0
                difference_y[position, ((row + 1) % height) * width + column] += 1.0
        matrix = np.eye(size) + beta * (
            difference_x.T @ difference_x + difference_y.T @ difference_y
        )
        rhs = input_image.ravel() + beta * (
            difference_x.T @ h.ravel() + difference_y.T @ v.ravel()
        )
        expected = np.linalg.solve(matrix, rhs).reshape(height, width)

        dx, dy = _frequency_responses(height, width)
        actual = _fft_update(
            np.fft.fft2(input_image)[..., None],
            h[..., None],
            v[..., None],
            beta,
            dx,
            dy,
        )[..., 0]
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)

    def test_rejects_invalid_input_and_parameters(self):
        valid = np.ones((2, 3), dtype=np.float64)
        with self.assertRaises(TypeError):
            smooth_l0(np.ones((2, 3), dtype=np.uint8))
        with self.assertRaises(ValueError):
            smooth_l0(np.ones((2, 3, 4), dtype=np.float64))
        with self.assertRaises(ValueError):
            smooth_l0(np.array([[1.1]], dtype=np.float64))
        with self.assertRaises(ValueError):
            smooth_l0(valid, lambda_=0)
        with self.assertRaises(ValueError):
            smooth_l0(valid, kappa=1)
        with self.assertRaises(ValueError):
            smooth_l0(valid, beta_max=0.04)


if __name__ == "__main__":
    unittest.main()
