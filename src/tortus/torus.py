"""Toroidal distance and projection utilities.

This module provides functions for calculating distances on a toroidal
manifold and projecting high-dimensional vectors onto 2D torus coordinates.
"""

import math

import numpy as np

from .models import ConceptNode, TorusCoordinate

TAU = 2.0 * math.pi


def angular_delta(left: float, right: float) -> float:
    """Calculate the shortest signed delta between two angles.

    Args:
        left: The first angle in radians.
        right: The second angle in radians.

    Returns:
        The shortest signed difference between the two angles, bounded by [-pi, pi].

    """
    return (left - right + math.pi) % TAU - math.pi


def torus_distance(left: TorusCoordinate, right: TorusCoordinate) -> float:
    """Calculate the shortest Euclidean distance on a toroidal surface.

    Args:
        left: The starting toroidal coordinate.
        right: The ending toroidal coordinate.

    Returns:
        The scalar distance between the two coordinates, accounting for wrap-around.

    """
    d_theta = angular_delta(left.theta, right.theta)
    d_phi = angular_delta(left.phi, right.phi)
    return math.sqrt(d_theta * d_theta + d_phi * d_phi)


class PeriodicStressProjector:
    """Map semantic vectors onto toroidal coordinates with a deterministic PCA-style seed."""

    def project(self, vectors: np.ndarray) -> list[TorusCoordinate]:
        """Project high-dimensional vectors onto a 2D toroidal coordinate space.

        Uses Singular Value Decomposition (SVD) to find the primary components,
        which are then scaled to the [0, 2*pi] range.

        Args:
            vectors: A 2D numpy array of embeddings (shape: [num_nodes, embedding_dim]).

        Returns:
            A list of TorusCoordinate objects corresponding to each input vector.

        Raises:
            ValueError: If the input array is not 2-dimensional.

        """
        if vectors.ndim != 2:
            raise ValueError("vectors must be a 2D matrix")
        if vectors.shape[0] == 0:
            return []
        centered = vectors - vectors.mean(axis=0, keepdims=True)
        if vectors.shape[0] == 1:
            coords = np.zeros((1, 2), dtype=np.float32)
        else:
            _, _, vh = np.linalg.svd(centered, full_matrices=False)
            basis = vh[:2].T
            if basis.shape[1] < 2:
                basis = np.pad(basis, ((0, 0), (0, 2 - basis.shape[1])))
            coords = centered @ basis[:, :2]
        return [
            TorusCoordinate(theta=float(theta), phi=float(phi))
            for theta, phi in scale_to_torus(coords)
        ]


def scale_to_torus(coords: np.ndarray) -> np.ndarray:
    """Scale arbitrary 2D coordinates into the toroidal range [0, 2*pi].

    Args:
        coords: A 2D numpy array of unscaled coordinates (shape: [num_nodes, 2]).

    Returns:
        A 2D numpy array of coordinates scaled between 0 and 2*pi.

    """
    scaled = np.zeros((coords.shape[0], 2), dtype=np.float64)
    for axis in range(2):
        values = coords[:, axis]
        min_value = float(values.min())
        max_value = float(values.max())
        if math.isclose(min_value, max_value):
            scaled[:, axis] = 0.0
        else:
            scaled[:, axis] = ((values - min_value) / (max_value - min_value)) * TAU
    return np.clip(scaled, 0.0, TAU)


def assign_torus(nodes: list[ConceptNode], vectors: np.ndarray) -> list[ConceptNode]:
    """Assign toroidal coordinates to a list of concept nodes.

    Args:
        nodes: The list of ConceptNode objects to update.
        vectors: The corresponding embeddings to project.

    Returns:
        A new list of ConceptNode objects with their `torus` fields populated.

    """
    coords = PeriodicStressProjector().project(vectors)
    assigned: list[ConceptNode] = []
    for node, coord in zip(nodes, coords, strict=True):
        assigned.append(node.model_copy(update={"torus": coord}))
    return assigned
