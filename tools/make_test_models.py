"""Create the test STL models in models/.

Usage:
    python tools/make_test_models.py
    python tools/make_test_models.py --sample path/to/downloaded.stl --url URL --author NAME --license "CC BY 4.0"

Makes cube30, cylinder30, sphere40, pyramid40 and broken_cube.
If --sample is given, the model is scaled so its longest side is 40 mm and saved as sample.stl.
"""
import argparse
import csv
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
SOURCES_CSV = MODELS_DIR / "sources.csv"
SAMPLE_LONG_SIDE_MM = 40.0
ALLOWED_LICENSES = ("CC0", "CC BY")  # ND (no derivatives) licenses are not allowed


def make_basic_models() -> dict:
    """Build the four basic shapes with trimesh. Returns {name: mesh}."""
    pyramid = trimesh.creation.cone(radius=28.3, height=30, sections=4)
    # A 4-sided cone has its corners on the X and Y axes. Rotate 45 deg so the base edges
    # are parallel to X and Y, which makes the base a 40 x 40 mm square.
    pyramid.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 4, [0, 0, 1]))
    return {
        "cube30": trimesh.creation.box((30, 30, 30)),
        "cylinder30": trimesh.creation.cylinder(radius=15, height=30, sections=96),
        "sphere40": trimesh.creation.icosphere(subdivisions=4, radius=20),
        "pyramid40": pyramid,
    }


def make_broken_cube() -> trimesh.Trimesh:
    """Return a 30 mm cube with one triangle removed, so it is not watertight."""
    cube = trimesh.creation.box((30, 30, 30))
    keep = np.ones(len(cube.faces), dtype=bool)
    keep[0] = False
    cube.update_faces(keep)
    cube.remove_unreferenced_vertices()
    return cube


def scale_sample(path: Path) -> trimesh.Trimesh:
    """Load a downloaded STL, scale it so the longest side is 40 mm, and move it to the origin."""
    mesh = trimesh.load(path, force="mesh")
    longest = float(max(mesh.extents))
    mesh.apply_scale(SAMPLE_LONG_SIDE_MM / longest)
    mesh.apply_translation(-mesh.bounds.mean(axis=0))
    return mesh


def check_and_save(name: str, mesh: trimesh.Trimesh, expect_watertight: bool = True) -> bool:
    """Check watertight and positive volume, then save to models/<name>.stl."""
    ok = mesh.is_watertight == expect_watertight
    if expect_watertight:
        ok = ok and mesh.volume > 0
    vol = f"{mesh.volume:.1f}" if mesh.is_watertight else "n/a"
    ext = " x ".join(f"{e:.1f}" for e in mesh.extents)
    status = "OK " if ok else "NG "
    print(f"{status} {name:12s} watertight={mesh.is_watertight!s:5s} volume={vol:>9s} mm3  size={ext} mm")
    if ok:
        mesh.export(MODELS_DIR / f"{name}.stl")
    return ok


def write_sources(sample_info: dict | None) -> None:
    """Write models/sources.csv with the origin and license of every model."""
    rows = [
        {"model": n, "source_url": "", "author": "generated with trimesh", "license": "own work", "notes": ""}
        for n in ("cube30", "cylinder30", "sphere40", "pyramid40", "broken_cube")
    ]
    if sample_info:
        rows.append(sample_info)
    elif SOURCES_CSV.exists():
        # Keep an existing sample row if the script is run again without --sample
        with open(SOURCES_CSV, newline="", encoding="utf-8") as f:
            rows += [r for r in csv.DictReader(f) if r["model"] == "sample"]
    with open(SOURCES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["model", "source_url", "author", "license", "notes"])
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    """Create all test models and report the result."""
    ap = argparse.ArgumentParser(description="Create test STL models in models/.")
    ap.add_argument("--sample", type=Path, help="downloaded STL to use as sample.stl")
    ap.add_argument("--url", default="", help="source URL of the sample model")
    ap.add_argument("--author", default="", help="author of the sample model")
    ap.add_argument("--license", default="", help="license of the sample model, e.g. 'CC BY 4.0'")
    args = ap.parse_args()

    MODELS_DIR.mkdir(exist_ok=True)
    all_ok = True
    for name, mesh in make_basic_models().items():
        all_ok &= check_and_save(name, mesh)
    all_ok &= check_and_save("broken_cube", make_broken_cube(), expect_watertight=False)

    sample_info = None
    if args.sample:
        if "ND" in args.license.upper() or not args.license.upper().startswith(ALLOWED_LICENSES):
            print("NG  sample: license must be CC0 or CC BY (no ND).")
            return 1
        sample = scale_sample(args.sample)
        if check_and_save("sample", sample):
            sample_info = {"model": "sample", "source_url": args.url, "author": args.author,
                           "license": args.license, "notes": f"scaled to {SAMPLE_LONG_SIDE_MM:.0f} mm long side"}
        else:
            print("    sample.stl is not watertight. Pick another model or repair it first.")
            all_ok = False
    elif not (MODELS_DIR / "sample.stl").exists():
        print("--  sample: not created yet. Run again with --sample.")

    write_sources(sample_info)
    print("All models OK." if all_ok else "Some models failed.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
