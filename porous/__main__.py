"""Command line: python -m porous input.stl --porosity 50 --out outputs/x.stl"""
import argparse
import sys
from pathlib import Path

from .core import (AXES, DEFAULT_CELL, DEFAULT_PITCH, MAX_POROSITY,
                   MIN_POROSITY, export, load_mesh, make_porous)


def check_range(value):
    """Stop if a porosity is outside the allowed range."""
    if not MIN_POROSITY <= value <= MAX_POROSITY:
        raise ValueError(
            f"Porosity must be between {MIN_POROSITY:g} and {MAX_POROSITY:g} %.")


def main(argv=None):
    """Parse the arguments, run the conversion and save the result."""
    ap = argparse.ArgumentParser(prog="python -m porous",
                                 description="Make a gyroid porous STL.")
    ap.add_argument("input", help="input STL file (closed mesh)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--porosity", type=float, help="uniform porosity in %%")
    mode.add_argument("--graded", nargs=3, metavar=("AXIS", "P_MIN", "P_MAX"),
                      help="graded porosity, e.g. Z 20 80")
    ap.add_argument("--cell", type=float, default=DEFAULT_CELL, help="cell size in mm")
    ap.add_argument("--pitch", type=float, default=DEFAULT_PITCH, help="voxel size in mm")
    ap.add_argument("--skin", type=float, default=0.0, help="solid skin thickness in mm")
    ap.add_argument("--out", help="output STL path (default: outputs/<name>_porous.stl)")

    def fail(message):
        """Print a usage error and exit with code 1 (not argparse's 2)."""
        ap.print_usage(sys.stderr)
        print(f"Error: {message}", file=sys.stderr)
        sys.exit(1)

    ap.error = fail
    args = ap.parse_args(argv)

    try:
        graded = None
        if args.graded:
            axis, p_min, p_max = args.graded[0].upper(), float(args.graded[1]), float(args.graded[2])
            if axis not in AXES:
                raise ValueError("Axis must be X, Y or Z.")
            check_range(p_min)
            check_range(p_max)
            graded = {"axis": axis, "p_min": p_min, "p_max": p_max}
        else:
            check_range(args.porosity)
        src = Path(args.input)
        out_path = Path(args.out) if args.out else Path("outputs") / f"{src.stem}_porous.stl"
        mesh = load_mesh(src)
        out, info = make_porous(mesh, porosity=args.porosity, graded=graded,
                                cell=args.cell, pitch=args.pitch, skin=args.skin)
        info["input"] = src.as_posix()
        export(out, info, out_path)
    except (ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    error = info["mesh_porosity"] - info["target"]
    note = "  (reached limit)" if info.get("reached_limit") else ""
    print(f"target {info['target']:.1f} / measured {info['mesh_porosity']:.1f} / "
          f"error {error:+.1f} / iterations {info['iterations']} / "
          f"{info['seconds']:.1f} s -> {out_path}{note}")


if __name__ == "__main__":
    main()