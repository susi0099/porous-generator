# App connection check (2026-10-27)

Checked by Ayumu with the final engine and the redesigned `app.py` (sidebar inputs, result tables).

| # | Case | Result | Notes |
|---|------|--------|-------|
| 1 | cube30, uniform 50% | OK | measured 49.1%, error -0.9, closed, 205,280 triangles, 1.9 s |
| 2 | sample, graded Z 20-80 | OK | target 45.8% (volume-weighted), measured 45.8%, largest band error 0.9 |
| 3 | pyramid40, uniform 65%, skin 0.5 mm | OK | measured 64.4%, error -0.6, bbox diff 0.28 mm |
| 4 | broken_cube.stl | OK | red error shown, app kept working |
| 5 | outputs in PrusaSlicer | OK | cube30 and sample open without warnings, pyramid40 sliced |

The numbers in cases 1 to 3 match `results/summary.csv` from `run_tests.py` (2026-10-26),
so the screen shows the same results as the command line.

## Screenshots

| File | What it shows |
|------|---------------|
| [app_sample_graded_z20-80_result.png](screenshots/app_sample_graded_z20-80_result.png) | Result tables for sample, graded Z 20-80 |
| [app_pyramid40_uniform65_skin0.5_result.png](screenshots/app_pyramid40_uniform65_skin0.5_result.png) | Result tables for pyramid40, 65%, skin 0.5 mm |
| [prusaslicer_cube30_uniform50.png](screenshots/prusaslicer_cube30_uniform50.png) | cube30 at 50% in PrusaSlicer |
| [prusaslicer_sample_graded_z20-80.png](screenshots/prusaslicer_sample_graded_z20-80.png) | sample (Spot), graded Z 20-80, in PrusaSlicer |
| [prusaslicer_pyramid40_skin0.5_sliced_top.png](screenshots/prusaslicer_pyramid40_skin0.5_sliced_top.png) | pyramid40 with a 0.5 mm skin, sliced, top view |
