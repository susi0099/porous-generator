"""Core functions for the porous structure generator."""
import json
import time
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage
from skimage.measure import marching_cubes

DEFAULT_CELL = 6.0        # gyroid period in mm
DEFAULT_PITCH = 0.5       # voxel size in mm
DEFAULT_TOL = 1.0         # allowed porosity error in points
DEFAULT_MAX_ITER = 8      # maximum calibration loops
MAX_VOXELS = 50_000_000   # memory limit for the voxel grid
MIN_POROSITY = 5.0        # lowest porosity the user can request (%)
MAX_POROSITY = 85.0       # highest porosity the user can request (%)
AXES = {"X": 0, "Y": 1, "Z": 2}
QS = np.linspace(0.01, 0.99, 99)  # porosity steps for the graded lookup table


def load_mesh(path) -> trimesh.Trimesh:
    """Load an STL file as one mesh.
    Raise ValueError if it has no triangles or is not closed."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Input file not found: {path}")
    mesh = trimesh.load(path, force="mesh")
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


def voxelize(mesh, pitch):
    """Voxelize the mesh and fill the inside.
    Returns the voxel grid and a bool array (True = inside)."""
    vg = mesh.voxelized(pitch).fill()
    return vg, np.asarray(vg.matrix, dtype=bool)


def axis_coords(vg, shape):
    """Return the mm coordinates of voxel centers along X, Y and Z."""
    scale = np.diag(vg.transform)[:3]
    offset = vg.transform[:3, 3]
    return [(offset[i] + np.arange(shape[i]) * scale[i]).astype(np.float32)
            for i in range(3)]


def gyroid_field(vg, shape, cell):
    """Gyroid value f at every voxel center (float32).
    Computed per axis and broadcast, so no huge point list is made."""
    k = np.float32(2 * np.pi / cell)
    x, y, z = [c * k for c in axis_coords(vg, shape)]
    sx, cx = np.sin(x)[:, None, None], np.cos(x)[:, None, None]
    sy, cy = np.sin(y)[None, :, None], np.cos(y)[None, :, None]
    sz, cz = np.sin(z)[None, None, :], np.cos(z)[None, None, :]
    return (sx * cy + sy * cz + sz * cx).astype(np.float32)


def keep_largest(mat):
    """Keep only the largest connected piece (fix 5).
    Returns the new mask and the number of removed pieces."""
    labels, n = ndimage.label(mat)
    if n <= 1:
        return mat, 0
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    return labels == sizes.argmax(), int(n - 1)


def to_mesh(mat, vg):
    """Turn the material voxels into a closed mesh (fix 2 and fix 3).
    Pads with empty voxels so the surface is closed at the edges."""
    verts, faces, _, _ = marching_cubes(np.pad(mat, 1).astype(np.uint8), level=0.5)
    verts = trimesh.transform_points(verts - 1, vg.transform)
    mesh = trimesh.Trimesh(verts, faces, process=True)
    if mesh.volume < 0:
        mesh.invert()
    return mesh


def make_porous(mesh, porosity=None, graded=None, cell=DEFAULT_CELL,
                pitch=DEFAULT_PITCH, skin=0.0, tol=DEFAULT_TOL,
                max_iter=DEFAULT_MAX_ITER, progress=None):
    """Convert a closed mesh into a gyroid porous mesh (temporary version).
    Uniform porosity only, no calibration yet (added on 10/22).
    Returns (output mesh, info dict in the JSON format of chapter 3)."""
    if porosity is None or graded is not None:
        raise ValueError("Graded porosity is not supported yet.")
    if skin > 0:
        raise ValueError("Skin is not supported yet.")
    report = progress or (lambda x: None)
    start = time.perf_counter()

    check_size(mesh, pitch)
    report(0.05)
    vg, solid = voxelize(mesh, pitch)
    f = gyroid_field(vg, solid.shape, cell)
    report(0.3)

    t = float(np.quantile(f[solid], porosity / 100))   # fix 1
    mat, removed = keep_largest(solid & (f > t))       # fix 5
    report(0.5)
    out = to_mesh(mat, vg)                             # fix 2 and 3
    report(0.95)

    info = {
        "input": str(mesh.metadata.get("file_path") or mesh.metadata.get("file_name") or ""),
        "mode": "uniform",
        "target": float(porosity),
        "graded": None,
        "cell": cell, "pitch": pitch, "skin": skin,
        "threshold": round(t, 4),
        "iterations": 1,
        "voxel_porosity": round(float((1 - mat.sum() / solid.sum()) * 100), 2),
        "mesh_porosity": round(float((1 - out.volume / mesh.volume) * 100), 2),
        "watertight": bool(out.is_watertight),
        "islands_removed": removed,
        "faces": int(len(out.faces)),
        "seconds": round(time.perf_counter() - start, 2),
    }
    report(1.0)
    return out, info


def export(mesh, info, path) -> None:
    """Save a binary STL and a JSON file with the same name."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(path, file_type="stl")  # binary STL
    path.with_suffix(".json").write_text(json.dumps(info, indent=2), encoding="utf-8")