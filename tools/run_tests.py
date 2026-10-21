"""Run all 38 tests from the spec: call the engine, check each output, write results/summary.csv.

Usage:
    python tools/run_tests.py                  # all 38 runs
    python tools/run_tests.py --group uniform  # only the 25 uniform runs (stage 1)
    python tools/run_tests.py --group pitch cell

Groups: uniform (25), graded (5), pitch (3), cell (3), skin (2).
"""
import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_stl import check  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
OUTPUTS_DIR = ROOT / "outputs"
SUMMARY_CSV = ROOT / "results" / "summary.csv"
CHECKS_CSV = ROOT / "results" / "checks.csv"

MODELS = ["cube30", "cylinder30", "sphere40", "pyramid40", "sample"]
UNIFORM_POROSITIES = [20, 35, 50, 65, 80]
GRADED = ("Z", 20, 80)
PITCHES = [0.8, 0.5, 0.3]
CELLS = [4, 6, 8]
SKIN_CASES = [("pyramid40", 65, 0.5), ("sample", 65, 0.5)]  # skin effect: bbox within 0.5 mm
DEFAULT_CELL = 6.0
DEFAULT_PITCH = 0.5
TIMEOUT_S = 900  # stop one run if it takes longer than this

SUMMARY_COLUMNS = ["test", "model", "setting", "engine_ok", "watertight", "mesh_porosity", "error",
                   "band_max_error", "parts", "bbox_diff_mm", "faces", "file_mb", "seconds", "pass",
                   "reasons", "message"]


def build_cases(groups: list[str]) -> list[dict]:
    """Return the list of test cases for the chosen groups."""
    cases = []
    if "uniform" in groups:
        for m in MODELS:
            for p in UNIFORM_POROSITIES:
                cases.append({"test": "uniform", "model": m, "porosity": p, "cell": DEFAULT_CELL,
                              "pitch": DEFAULT_PITCH, "out": f"{m}_p{p}.stl", "setting": f"{p}%"})
    if "graded" in groups:
        axis, lo, hi = GRADED
        for m in MODELS:
            cases.append({"test": "graded", "model": m, "graded": GRADED, "cell": DEFAULT_CELL,
                          "pitch": DEFAULT_PITCH, "out": f"{m}_g{axis}_{lo}_{hi}.stl",
                          "setting": f"{axis} {lo}->{hi}%"})
    if "pitch" in groups:
        for pt in PITCHES:
            cases.append({"test": "pitch", "model": "cube30", "porosity": 50, "cell": DEFAULT_CELL,
                          "pitch": pt, "out": f"cube30_p50_pitch{pt}.stl", "setting": f"pitch {pt}"})
    if "cell" in groups:
        for c in CELLS:
            cases.append({"test": "cell", "model": "cube30", "porosity": 50, "cell": float(c),
                          "pitch": DEFAULT_PITCH, "out": f"cube30_p50_cell{c}.stl", "setting": f"cell {c}"})
    if "skin" in groups:
        for m, p, s in SKIN_CASES:
            cases.append({"test": "skin", "model": m, "porosity": p, "cell": DEFAULT_CELL,
                          "pitch": DEFAULT_PITCH, "skin": s, "out": f"{m}_p{p}_skin{s}.stl",
                          "setting": f"{p}% skin {s}"})
    return cases


def run_engine(case: dict) -> tuple[bool, str]:
    """Call 'python -m porous ...' for one case. Returns (success, last line of output)."""
    src = MODELS_DIR / f"{case['model']}.stl"
    cmd = [sys.executable, "-m", "porous", str(src), "--out", str(OUTPUTS_DIR / case["out"]),
           "--cell", str(case["cell"]), "--pitch", str(case["pitch"])]
    if "graded" in case:
        cmd += ["--graded"] + [str(v) for v in case["graded"]]
    else:
        cmd += ["--porosity", str(case["porosity"])]
    if case.get("skin"):
        cmd += ["--skin", str(case["skin"])]
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return False, f"timeout after {TIMEOUT_S} s"
    text = (r.stdout + r.stderr).strip().splitlines()
    return r.returncode == 0, (text[-1] if text else "")


def main() -> int:
    """Run the chosen tests and print a summary table."""
    ap = argparse.ArgumentParser(description="Run engine tests and check every output.")
    ap.add_argument("--group", nargs="+", default=["uniform", "graded", "pitch", "cell", "skin"],
                    choices=["uniform", "graded", "pitch", "cell", "skin"])
    args = ap.parse_args()

    missing = [m for m in MODELS if not (MODELS_DIR / f"{m}.stl").exists()]
    if missing:
        print(f"Missing models: {', '.join(missing)}. Run tools/make_test_models.py first.")
        return 1
    OUTPUTS_DIR.mkdir(exist_ok=True)

    cases = build_cases(args.group)
    rows = []
    t_start = time.time()
    for i, case in enumerate(cases, 1):
        print(f"[{i:2d}/{len(cases)}] {case['test']:7s} {case['model']:10s} {case['setting']:12s} ", end="", flush=True)
        ok, msg = run_engine(case)
        row = {k: "" for k in SUMMARY_COLUMNS}
        row.update({"test": case["test"], "model": case["model"], "setting": case["setting"],
                    "engine_ok": ok, "message": msg})
        if ok:
            res = check(MODELS_DIR / f"{case['model']}.stl", OUTPUTS_DIR / case["out"],
                        porosity_target=case.get("porosity"), graded=case.get("graded"),
                        csv_path=CHECKS_CSV, verbose=False)
            for k in SUMMARY_COLUMNS:
                if k in res:
                    row[k] = res[k]
        else:
            row["pass"] = False
            row["reasons"] = "engine error"
        rows.append(row)
        err = f"{row['error']:+.1f}" if row["error"] != "" else "  -  "
        print(f"{'PASS' if row['pass'] else 'FAIL'}  error {err}  {row['seconds']} s")

    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_csv = SUMMARY_CSV
    try:
        f = open(out_csv, "w", newline="", encoding="utf-8")
    except PermissionError:
        # Usually the file is open in Excel. Save under another name instead of losing the results.
        out_csv = SUMMARY_CSV.with_name(f"summary_{time.strftime('%Y%m%d_%H%M%S')}.csv")
        print(f"\n{SUMMARY_CSV.name} is open in another program (Excel?). Close it next time.")
        f = open(out_csv, "w", newline="", encoding="utf-8")
    with f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        w.writeheader()
        w.writerows(rows)

    n_pass = sum(bool(r["pass"]) for r in rows)
    print(f"\n{n_pass}/{len(rows)} passed in {time.time() - t_start:.0f} s. Saved {out_csv.relative_to(ROOT)}")
    for r in rows:
        if not r["pass"]:
            print(f"  FAIL {r['test']} {r['model']} {r['setting']}: {r['reasons']}  [{r['message']}]")
    return 0 if n_pass == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
