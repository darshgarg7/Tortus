import math

import numpy as np

from tortus.models import TorusCoordinate
from tortus.torus import PeriodicStressProjector, torus_distance


def test_torus_distance_wraps_across_boundary() -> None:
    left = TorusCoordinate(theta=0.02, phi=1.0)
    right = TorusCoordinate(theta=2 * math.pi - 0.02, phi=1.0)
    assert torus_distance(left, right) < 0.05


def test_projector_returns_one_coordinate_per_vector() -> None:
    vectors = np.eye(4, dtype=np.float32)
    coords = PeriodicStressProjector().project(vectors)
    assert len(coords) == 4
    assert all(0.0 <= coord.theta <= 2 * math.pi for coord in coords)
    assert all(0.0 <= coord.phi <= 2 * math.pi for coord in coords)
