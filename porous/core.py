"""Core functions for the porous structure generator."""
import json
import time
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage
from skimage.measure import marching_cubes

from .calibrate import calibrate, calibrate_bands, load_table, threshold_from_table

DEFAULT_CELL = 6.0        # gyroid period in mm
DEFAULT_PITCH = 0.5       # voxel size in mm
DEFAULT_TOL = 1.0         # allowed porosity error in points
DEFAULT_MAX_ITER = 8      # maximum calibration loops
MAX_VOXELS = 50_000_000   # memory limit for the voxel grid
MIN_POROSITY = 5.0        # lowest porosity the user can request (%)
MAX_POROSITY = 85.0       # highest porosity the user can request (%)
AXES = {"X": 0, "Y": 1, "Z": 2}
N_BANDS = 5              # graded: number of equal bands along the axis
GYROID_PHASE = (0.137, 0.291, 0.419)  # pattern shift in cells, breaks ties (see gyroid_field)
MC_LEVEL = 0.45          # surface level for marching cubes (not 0.5, see to_mesh)


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
    Computed per axis and broadcast, so no huge point list is made.
    The pattern is shifted by GYROID_PHASE so that voxel centers do not sit on
    its symmetry points; otherwise f has only a few values and porosity jumps."""
    k = np.float32(2 * np.pi / cell)
    x, y, z = [(c + np.float32(ph * cell)) * k
               for c, ph in zip(axis_coords(vg, shape), GYROID_PHASE)]
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
    Pads with empty voxels so the surface is closed at the edges.
    Level 0.5 is an exact tie for 0/1 voxels, which can make edges shared
    by 3 or more faces (not watertight), so MC_LEVEL is used instead."""
    verts, faces, _, _ = marching_cubes(np.pad(mat, 1).astype(np.uint8), level=MC_LEVEL)
    verts = trimesh.transform_points(verts - 1, vg.transform)
    mesh = trimesh.Trimesh(verts, faces, process=True)
    if mesh.volume < 0:
        mesh.invert()
    return mesh

def band_volumes(mesh, axis, edges):
    """Volume of each band, cut with two planes like check_stl.py."""
    normal = np.eye(3)[axis]
    volumes = []
    for a, b in zip(edges[:-1], edges[1:]):
        origin = np.zeros(3)
        origin[axis] = a
        part = mesh.slice_plane(origin, normal, cap=True)
        origin[axis] = b
        part = part.slice_plane(origin, -normal, cap=True)
        volumes.append(part.volume)
    return np.array(volumes)


def make_porous(mesh, porosity=None, graded=None, cell=DEFAULT_CELL,
                pitch=DEFAULT_PITCH, skin=0.0, tol=DEFAULT_TOL,
                max_iter=DEFAULT_MAX_ITER, progress=None):
    """Convert a closed mesh into a gyroid porous mesh.
    Give porosity (%) or graded ({"axis": "Z", "p_min": 20, "p_max": 80}).
        skin (mm) keeps a solid outer layer of that thickness.
    Returns (output mesh, info dict in the JSON format of chapter 3)."""
    if (porosity is None) == (graded is None):
        raise ValueError("Give either porosity or graded, not both.")
    if skin < 0:
        raise ValueError("Skin must be 0 or more.")
    report = progress or (lambda x: None)
    start = time.perf_counter()
    table = load_table()

    # Steps 2-4: done once, outside the calibration loop
    check_size(mesh, pitch)
    report(0.05)
    vg, solid = voxelize(mesh, pitch)
    f = gyroid_field(vg, solid.shape, cell)

    # Skin (work 4): voxels within `skin` mm of the surface are always material
    shell = None
    if skin > 0:
        # Pad with empty voxels so the array edge counts as outside
        dist = ndimage.distance_transform_edt(np.pad(solid, 1), sampling=pitch)
        shell = solid & (dist[1:-1, 1:-1, 1:-1] <= skin)
    report(0.2)

    calls = {"n": 0}

    def finish(t):
        """Steps 5-8 for a threshold t (number or array that broadcasts)."""
        mat = solid & (f > t)
        if shell is not None:
            mat |= shell                                   # add the skin before calibration
        mat, removed = keep_largest(mat)                   # fix 5
        out = to_mesh(mat, vg)                             # fix 2 and 3
        calls["n"] += 1
        report(min(0.2 + 0.1 * calls["n"], 0.95))
        voxel_p = (1 - mat.sum() / solid.sum()) * 100
        return out, {"voxel_porosity": voxel_p, "islands_removed": removed}

    if graded is None:
        target = float(porosity)
        t_first = float(threshold_from_table(target, table))

        def build(request):
            """Uniform: one threshold from the table (fix 1)."""
            t = float(threshold_from_table(request, table))
            out, extra = finish(t)
            extra["threshold"] = t
            return out, extra

        best = calibrate(build, target, mesh.volume, tol, max_iter)
        measured = best["measured"]
    else:
        axis = AXES[graded["axis"].upper()]
        p_min, p_max = float(graded["p_min"]), float(graded["p_max"])
        lo, hi = mesh.bounds[0][axis], mesh.bounds[1][axis]
        c = axis_coords(vg, solid.shape)[axis]
        p_line = p_min + (p_max - p_min) * np.clip((c - lo) / (hi - lo), 0, 1)
        view = [None, None, None]
        view[axis] = slice(None)
        view = tuple(view)
        # Total target: volume-weighted average of p(c) over the inside voxels
        p_inside = np.broadcast_to(p_line[view], solid.shape)[solid]
        target = float(p_inside.mean())
        edges = np.linspace(lo, hi, N_BANDS + 1)
        centers = (edges[:-1] + edges[1:]) / 2
        # Band targets: p(c) at the band centers, the same as check_stl.py
        band_targets = p_min + (p_max - p_min) * (centers - lo) / (hi - lo)
        original_volumes = band_volumes(mesh, axis, edges)
        t_first = None

        def build(corrections):
            """Graded: threshold per slice from the table, plus band corrections."""
            p = np.clip(p_line + np.interp(c, centers, corrections), 1, 99)
            t_line = threshold_from_table(p, table).astype(np.float32)
            out, extra = finish(t_line[view])
            extra["threshold"] = None
            return out, extra

        def measure(out):
            """Band porosities of the output mesh."""
            return (1 - band_volumes(out, axis, edges) / original_volumes) * 100

        best = calibrate_bands(build, measure, band_targets, tol, max_iter)
        measured = (1 - best["mesh"].volume / mesh.volume) * 100

    out, extra = best["mesh"], best["extra"]
    info = {
        "input": str(mesh.metadata.get("file_path") or mesh.metadata.get("file_name") or ""),
        "mode": "uniform" if graded is None else "graded",
        "target": round(target, 2),
        "graded": None if graded is None else {
            "axis": graded["axis"].upper(), "p_min": p_min, "p_max": p_max},
        "cell": cell, "pitch": pitch, "skin": skin,
        "threshold_initial": None if t_first is None else round(t_first, 4),
        "threshold": None if extra["threshold"] is None else round(extra["threshold"], 4),
        "iterations": best["iterations"],
        "voxel_porosity": round(float(extra["voxel_porosity"]), 2),
        "mesh_porosity": round(float(measured), 2),
        "band_max_error": None if graded is None else round(best["band_max_error"], 2),
        "watertight": bool(out.is_watertight),
        "islands_removed": extra["islands_removed"],
        "faces": int(len(out.faces)),
        "seconds": round(time.perf_counter() - start, 2),
    }
    if best["reached_limit"]:
        info["reached_limit"] = True
    report(1.0)
    return out, info

def export(mesh, info, path) -> None:
    """Save a binary STL and a JSON file with the same name."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(path, file_type="stl")  # binary STL
    path.with_suffix(".json").write_text(json.dumps(info, indent=2), encoding="utf-8")