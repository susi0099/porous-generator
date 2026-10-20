"""Command line (temporary): python -m porous input.stl --porosity 50 --out outputs/x.stl"""
import argparse
import sys
from pathlib import Path

from .core import DEFAULT_CELL, DEFAULT_PITCH, export, load_mesh, make_porous


def main(argv=None):
    """Parse the arguments, run the conversion and save the result."""
    ap = argparse.ArgumentParser(prog="python -m porous",
                                 description="Make a gyroid porous STL.")
    ap.add_argument("input", help="input STL file (closed mesh)")
    ap.add_argument("--porosity", type=float, required=True, help="porosity in %%")
    ap.add_argument("--cell", type=float, default=DEFAULT_CELL, help="cell size in mm")
    ap.add_argument("--pitch", type=float, default=DEFAULT_PITCH, help="voxel size in mm")
    ap.add_argument("--out", help="output STL path (default: outputs/<name>_porous.stl)")
    args = ap.parse_args(argv)

    src = Path(args.input)
    out_path = Path(args.out) if args.out else Path("outputs") / f"{src.stem}_porous.stl"
    try:
        mesh = load_mesh(src)
        out, info = make_porous(mesh, porosity=args.porosity,
                                cell=args.cell, pitch=args.pitch)
        info["input"] = src.as_posix()
        export(out, info, out_path)
    except (ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    error = info["mesh_porosity"] - info["target"]
    print(f"target {info['target']:.1f} / measured {info['mesh_porosity']:.1f} / "
          f"error {error:+.1f} / {info['seconds']:.1f} s -> {out_path}")


if __name__ == "__main__":
    main()