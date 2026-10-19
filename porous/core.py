"""Core functions for the porous structure generator."""
from pathlib import Path

import numpy as np
import trimesh

DEFAULT_CELL = 6.0        # gyroid period in mm
DEFAULT_PITCH = 0.5       # voxel size in mm
DEFAULT_TOL = 1.0         # allowed porosity error in points
DEFAULT_MAX_ITER = 8      # maximum calibration loops
MAX_VOXELS = 50_000_000   # memory limit for the voxel grid
MIN_POROSITY = 5.0        # lowest porosity the user can request (%)
MAX_POROSITY = 85.0       # highest porosity the user can request (%)


def load_mesh(path) -> trimesh.Trimesh:
    """Load an STL file as one mesh.
    Raise ValueError if it has no triangles or is not closed."""
    mesh = trimesh.load(Path(path), force="mesh")
    if len(mesh.faces) == 0 or not mesh.is_watertight:
        raise ValueError("Input STL is not watertight. Please repair the mesh.")
    return mesh


def check_size(mesh: trimesh.Trimesh, pitch: float) -> int:
    """Estimate the number of voxels and stop if it is too large.
    Returns the estimated voxel count."""
    count = int(np.prod(np.ceil(mesh.extents / pitch)))
    if count > MAX_VOXELS:
        raise ValueError("Model too large: increase the voxel pitch.")
    return count