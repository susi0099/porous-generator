"""Independently check one output STL against its original and append a row to results/checks.csv.

Usage:
    python tools/check_stl.py models/cube30.stl outputs/cube_p50.stl --porosity 50
    python tools/check_stl.py models/cube30.stl outputs/cube_g.stl --graded Z 20 80

Porosity is measured only from the two STL files (mesh.volume). The engine's own numbers are
never used for pass/fail. Only faces, seconds, cell, pitch and skin are read from the JSON
that has the same name as the output STL.
"""
import argparse
import csv
import json
from datetime import date
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
CHECKS_CSV = ROOT / "results" / "checks.csv"

# Pass conditions (spec chapter 4, task 2)
MAX_ERROR = 3.0          # points, overall porosity
MAX_BAND_ERROR = 5.0     # points, each band in graded mode
MAX_BBOX_DIFF_MM = 1.0
N_BANDS = 5
N_SLICES_FOR_TARGET = 20  # thin slices used to find the volume-weighted graded target

COLUMNS = ["date", "model", "mode", "target", "cell", "pitch", "watertight", "mesh_porosity",
           "error", "band_max_error", "parts", "bbox_diff_mm", "faces", "file_mb", "seconds", "pass"]
AXES = {"X": 0, "Y": 1, "Z": 2}


def load_stl(path: Path) -> trimesh.Trimesh:
    """Load an STL as a single mesh without repairing it."""
    return trimesh.load(path, force="mesh")


def read_info(out_path: Path) -> dict:
    """Read the engine JSON next to the output STL. Returns {} if it does not exist."""
    js = out_path.with_suffix(".json")
    if js.exists():
        return json.loads(js.read_text(encoding="utf-8"))
    return {}


def porosity(original_volume: float, output_volume: float) -> float:
    """Porosity in % = (1 - output volume / original volume) * 100."""
    return (1.0 - output_volume / original_volume) * 100.0


def cut_band(mesh: trimesh.Trimesh, axis: int, lo: float, hi: float) -> trimesh.Trimesh:
    """Cut the part of the mesh between lo and hi along one axis, closing the cut faces."""
    normal = np.zeros(3)
    normal[axis] = 1.0
    origin_lo = np.zeros(3)
    origin_lo[axis] = lo
    origin_hi = np.zeros(3)
    origin_hi[axis] = hi
    part = mesh.slice_plane(origin_lo, normal, cap=True)       # keep side above lo
    part = part.slice_plane(origin_hi, -normal, cap=True)      # keep side below hi
    return part


def graded_overall_target(original, axis_name, p_min, p_max) -> float:
    """Volume-weighted average of p(c) over the original model.

    For a cube or cylinder this equals (p_min + p_max) / 2. For a pyramid most of the volume is
    near the base, so the true overall target is lower than the simple average.
    """
    axis = AXES[axis_name]
    c_min, c_max = original.bounds[0, axis], original.bounds[1, axis]
    edges = np.linspace(c_min, c_max, N_SLICES_FOR_TARGET + 1)
    total = weighted = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        v = cut_band(original, axis, lo, hi).volume
        centre = (lo + hi) / 2
        weighted += v * (p_min + (p_max - p_min) * (centre - c_min) / (c_max - c_min))
        total += v
    return weighted / total


def band_errors(original, output, axis_name, p_min, p_max) -> list[dict]:
    """Split the axis into 5 equal bands and compare measured porosity with p(c) at each band centre."""
    axis = AXES[axis_name]
    c_min, c_max = original.bounds[0, axis], original.bounds[1, axis]
    edges = np.linspace(c_min, c_max, N_BANDS + 1)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        v_orig = cut_band(original, axis, lo, hi).volume
        v_out = cut_band(output, axis, lo, hi).volume
        centre = (lo + hi) / 2
        target = p_min + (p_max - p_min) * (centre - c_min) / (c_max - c_min)
        measured = porosity(v_orig, v_out)
        rows.append({"from": lo, "to": hi, "target": target, "measured": measured, "error": measured - target})
    return rows


def check(original_path, output_path, porosity_target=None, graded=None, csv_path=CHECKS_CSV,
          verbose=True) -> dict:
    """Run all checks, append one row to checks.csv and return the row as a dict.

    The returned dict also has "reasons" (why it failed), which is not written to checks.csv.
    """
    original_path, output_path = Path(original_path), Path(output_path)
    original = load_stl(original_path)
    output = load_stl(output_path)
    info = read_info(output_path)

    if graded:
        axis_name, p_min, p_max = graded[0].upper(), float(graded[1]), float(graded[2])
        mode = "graded"
        target = graded_overall_target(original, axis_name, p_min, p_max)
    else:
        mode, target = "uniform", float(porosity_target)

    skin = float(info.get("skin", 0.0) or 0.0)
    row = {k: "" for k in COLUMNS}
    row.update({
        "date": date.today().isoformat(),
        "model": original_path.stem,
        "mode": mode,
        "target": round(target, 1),
        "cell": info.get("cell", ""),
        "pitch": info.get("pitch", ""),
        "watertight": bool(output.is_watertight),
        "faces": info.get("faces", len(output.faces)),
        "file_mb": round(output_path.stat().st_size / 1e6, 1),
        "seconds": info.get("seconds", ""),
    })
    bbox_diff = float(np.abs(output.bounds - original.bounds).max())
    row["bbox_diff_mm"] = round(bbox_diff, 2)

    if not output.is_watertight:
        # Volume of an open mesh is meaningless, so stop here.
        row["pass"] = False
        row["reasons"] = "not watertight"
        _append(csv_path, row)
        if verbose:
            print(f"FAIL {output_path.name}: output is not watertight, volume not measured.")
        return row

    measured = porosity(original.volume, output.volume)
    error = measured - target
    parts = int(output.body_count)
    row.update({"mesh_porosity": round(measured, 1), "error": round(error, 1), "parts": parts})

    reasons = []
    if abs(error) > MAX_ERROR:
        reasons.append(f"error {error:+.1f}")
    if bbox_diff > MAX_BBOX_DIFF_MM:
        reasons.append(f"bbox diff {bbox_diff:.2f} mm")
    if skin == 0 and parts != 1:  # with a skin the inner void is also counted, so skip this check
        reasons.append(f"{parts} parts")

    bands = []
    if graded:
        bands = band_errors(original, output, axis_name, p_min, p_max)
        band_max = max(abs(b["error"]) for b in bands)
        row["band_max_error"] = round(band_max, 1)
        if band_max > MAX_BAND_ERROR:
            reasons.append(f"band error {band_max:.1f}")

    ok = not reasons
    row["pass"] = ok
    row["reasons"] = "; ".join(reasons)
    _append(csv_path, row)

    if verbose:
        print(f"{'PASS' if ok else 'FAIL'} {output_path.name}" + (f"  ({row['reasons']})" if reasons else ""))
        print(f"  watertight   {output.is_watertight}")
        print(f"  porosity     {measured:.1f}% (target {target:.1f}%, error {error:+.1f})")
        print(f"  parts        {parts}" + ("  (not judged: skin > 0)" if skin else ""))
        print(f"  bbox diff    {bbox_diff:.2f} mm")
        for b in bands:
            print(f"  band {b['from']:7.2f} to {b['to']:7.2f}: {b['measured']:5.1f}% "
                  f"(target {b['target']:.1f}, error {b['error']:+.1f})")
    return row


def _append(csv_path: Path, row: dict) -> None:
    """Append one row to the CSV, writing the header if the file is new."""
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    new = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")  # "reasons" is not saved
        if new:
            w.writeheader()
        w.writerow(row)


def main() -> int:
    """Command line entry point."""
    ap = argparse.ArgumentParser(description="Check an output STL against its original STL.")
    ap.add_argument("original", type=Path, help="original STL")
    ap.add_argument("output", type=Path, help="porous STL made by the engine")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--porosity", type=float, help="target porosity in %% (uniform mode)")
    g.add_argument("--graded", nargs=3, metavar=("AXIS", "P_MIN", "P_MAX"),
                   help="graded mode, e.g. --graded Z 20 80")
    ap.add_argument("--csv", type=Path, default=CHECKS_CSV, help="CSV file to append to")
    args = ap.parse_args()
    if args.graded and args.graded[0].upper() not in AXES:
        ap.error("AXIS must be X, Y or Z")
    row = check(args.original, args.output, args.porosity, args.graded, args.csv)
    return 0 if row["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
