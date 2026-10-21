"""Calibration table (porosity -> threshold) and output-volume calibration (fix 4)."""
import argparse
from pathlib import Path

import numpy as np

TABLE_PATH = Path(__file__).with_name("calibration.csv")
TABLE_POINTS = 100   # points per side for one gyroid period
REQUEST_MIN = 1.0    # lowest porosity request sent to build()
REQUEST_MAX = 99.0   # highest porosity request sent to build()


def build_table(points=TABLE_POINTS, path=TABLE_PATH):
    """Sample one gyroid period and save porosity (1-99 %) and threshold t."""
    g = np.arange(points) / points * 2 * np.pi
    x, y, z = g[:, None, None], g[None, :, None], g[None, None, :]
    f = np.sin(x) * np.cos(y) + np.sin(y) * np.cos(z) + np.sin(z) * np.cos(x)
    porosity = np.arange(1, 100, dtype=float)
    threshold = np.quantile(f, porosity / 100)
    rows = "\n".join(f"{p:g},{t:.6f}" for p, t in zip(porosity, threshold))
    Path(path).write_text("porosity,threshold\n" + rows + "\n", encoding="utf-8")
    return porosity, threshold


def load_table(path=TABLE_PATH):
    """Read the table. Build it first if the file does not exist."""
    if not Path(path).is_file():
        return build_table(path=path)
    data = np.loadtxt(path, delimiter=",", skiprows=1)
    return data[:, 0], data[:, 1]


def threshold_from_table(porosity, table):
    """Look up the threshold t for a porosity (%) or an array of porosities."""
    p_table, t_table = table
    return np.interp(porosity, p_table, t_table)


def next_request(request, measured, target, below, above):
    """Choose the next request. Step by the error, but stay between the
    best requests found below and above the target (bracketing).
    This avoids jumping back and forth when porosity changes in steps."""
    new = request + (target - measured)
    if below is not None and above is not None:
        lo, hi = sorted((below[0], above[0]))
        if not lo < new < hi:
            # Secant guess inside the bracket, or the middle if it is flat
            (r1, m1), (r2, m2) = below, above
            new = r1 + (target - m1) * (r2 - r1) / (m2 - m1) if m2 != m1 else (lo + hi) / 2
            if not lo < new < hi:
                new = (lo + hi) / 2
    return float(np.clip(new, REQUEST_MIN, REQUEST_MAX))


def calibrate(build, target, original_volume, tol, max_iter):
    """Uniform: call build(request) until the measured porosity is within tol.
    build returns (mesh, extra). Returns a dict with the best result."""
    request = float(target)
    best = None
    below = above = None  # (request, measured) closest to target on each side
    for i in range(1, max_iter + 1):
        mesh, extra = build(request)
        measured = (1 - mesh.volume / original_volume) * 100
        if best is None or abs(measured - target) < abs(best["measured"] - target):
            best = {"mesh": mesh, "extra": extra, "measured": measured}
        best["iterations"] = i
        if abs(measured - target) <= tol:
            best["reached_limit"] = False
            return best
        if measured < target and (below is None or measured > below[1]):
            below = (request, measured)
        if measured > target and (above is None or measured < above[1]):
            above = (request, measured)
        new = next_request(request, measured, target, below, above)
        if abs(new - request) < 1e-6:  # stuck at 1 or 99, or no room left
            break
        request = new
    best["reached_limit"] = True
    return best


def main(argv=None):
    """python -m porous.calibrate --build : make calibration.csv."""
    ap = argparse.ArgumentParser(prog="python -m porous.calibrate")
    ap.add_argument("--build", action="store_true", help="build calibration.csv")
    args = ap.parse_args(argv)
    if args.build:
        p, t = build_table()
        print(f"saved {TABLE_PATH} ({len(p)} rows, t from {t[0]:.3f} to {t[-1]:.3f})")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()