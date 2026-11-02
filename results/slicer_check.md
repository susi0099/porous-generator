# Slicer check (2026-11-02)

Checked by Yoshinaga in PrusaSlicer 2.9.6.
Printer: Prusa CORE One MMU3, **0.4 mm nozzle**. Print settings: 0.10 mm FAST DETAIL, Generic PETG.
The files are the ones in `examples/` (cell 6 mm, pitch 0.5 mm, no skin).

| File | Opened | Sliced | Notes |
|------|--------|--------|-------|
| `cube30_uniform20.stl` | OK, "no errors detected", 1 shell, 197,500 faces | OK, 3 h 48 min | walls are thick enough for perimeters and infill |
| `cube30_uniform50.stl` | OK, no warnings | OK | checked on 2026-10-27, see `app_check.md` |
| `cube30_uniform80.stl` | OK, "no errors detected", 1 shell, 156,760 faces | OK, 2 h 26 min | walls are made of perimeter lines only (no infill fits), but no line is broken |
| `sample_graded_z20-80.stl` | OK, no warnings | OK | checked on 2026-10-27, see `app_check.md` |

## Walls at 80 %

At 80 % the walls are thin. In the slice preview at mid height (layer 145, 14.6 mm)
the slicer uses only perimeter and external perimeter lines, with no infill.
The lines are continuous around every pore, and the side view shows no gaps between layers.
So the 80 % cube can be printed with a 0.4 mm nozzle, but it has little margin.
For higher porosity or smaller cells, check the preview again.

## Screenshots

| File | What it shows |
|------|---------------|
| [prusaslicer_cube30_uniform20_sliced.png](screenshots/prusaslicer_cube30_uniform20_sliced.png) | 20 %, sliced, cut at mid height |
| [prusaslicer_cube30_uniform20_walls.png](screenshots/prusaslicer_cube30_uniform20_walls.png) | 20 %, side view of the layers |
| [prusaslicer_cube30_uniform80_sliced.png](screenshots/prusaslicer_cube30_uniform80_sliced.png) | 80 %, sliced, cut at mid height |
| [prusaslicer_cube30_uniform80_walls.png](screenshots/prusaslicer_cube30_uniform80_walls.png) | 80 %, side view of the thin walls |
| [prusaslicer_cube30_uniform50.png](screenshots/prusaslicer_cube30_uniform50.png) | 50 %, opened |
| [prusaslicer_sample_graded_z20-80.png](screenshots/prusaslicer_sample_graded_z20-80.png) | cow, graded Z 20 → 80 %, opened |
