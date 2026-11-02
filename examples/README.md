# Example outputs

Six porous STL files made with the Porous Structure Generator.
All use a gyroid lattice with **cell 6 mm** and **voxel pitch 0.5 mm**, and no skin.
Every file passed `tools/check_stl.py`, which measures the STL files themselves
and does not use the numbers the engine prints.

Porosity = (1 − output volume ÷ input volume) × 100, measured with `trimesh`.

## Files

| File | Input model | Setting | Measured porosity | Error | Triangles | File size |
|------|-------------|---------|------------------:|------:|----------:|----------:|
| `cube30_uniform20.stl` | `models/cube30.stl` | uniform 20 % | 20.9 % | +0.9 pt | 197,500 | 9.9 MB |
| `cube30_uniform50.stl` | `models/cube30.stl` | uniform 50 % | 49.1 % | −0.9 pt | 205,280 | 10.3 MB |
| `cube30_uniform80.stl` | `models/cube30.stl` | uniform 80 % | 79.2 % | −0.8 pt | 156,760 | 7.8 MB |
| `cube30_graded_z20-80.stl` | `models/cube30.stl` | graded along Z, 20 % at the bottom to 80 % at the top | 49.4 % (target 50.0 %) | −0.6 pt | 192,428 | 9.6 MB |
| `sample_uniform50.stl` | `models/sample.stl` | uniform 50 % | 50.2 % | +0.2 pt | 77,768 | 3.9 MB |
| `sample_graded_z20-80.stl` | `models/sample.stl` | graded along Z, 20 % at the bottom to 80 % at the top | 45.8 % (target 45.8 %) | 0.0 pt | 77,812 | 3.9 MB |

For graded files the target is the volume-weighted porosity. It equals the simple
average (50 %) only when the volume is spread evenly along the axis, as in the cube.
The cow in `sample.stl` has more volume in its lower half, so its target is 45.8 %.

### Graded files: porosity in 5 bands along Z

| File | Band 1 (bottom) | Band 2 | Band 3 | Band 4 | Band 5 (top) | Largest band error |
|------|----:|----:|----:|----:|----:|----:|
| `cube30_graded_z20-80.stl` | 26.3 % | 38.1 % | 50.1 % | 62.3 % | 74.2 % | 0.3 pt |
| `sample_graded_z20-80.stl` | 26.0 % | 38.3 % | 49.5 % | 62.2 % | 73.1 % | 0.9 pt |
| Target | 26.0 % | 38.0 % | 50.0 % | 62.0 % | 74.0 % | limit ±5 pt |

## Check results

All six files are closed (watertight) and are one piece.
The porosity error is within ±1 point, well inside the ±3 point limit.

The outer size of the cube files differs from the input by 0.27 mm at most (limit 1.0 mm).
For `sample.stl` this value is only recorded, because the cow has thin parts such as
the ears and horns. In `sample_graded_z20-80.stl` the top band is 74 % porous and
some of these thin parts are lost, so the outer size differs by 2.41 mm.
To keep them when printing, add a solid skin of 0.5 mm (`--skin 0.5`).

Checked on 2026-11-02. The numbers match `results/summary.csv`.

## How to make them again

Run from the repository root with the virtual environment active.

```
python -m porous models/cube30.stl --porosity 20 --out examples/cube30_uniform20.stl
python -m porous models/cube30.stl --porosity 50 --out examples/cube30_uniform50.stl
python -m porous models/cube30.stl --porosity 80 --out examples/cube30_uniform80.stl
python -m porous models/cube30.stl --graded Z 20 80 --out examples/cube30_graded_z20-80.stl
python -m porous models/sample.stl --porosity 50 --out examples/sample_uniform50.stl
python -m porous models/sample.stl --graded Z 20 80 --out examples/sample_graded_z20-80.stl
```

Cell 6 mm and pitch 0.5 mm are the defaults, so they are not written above.
Each command also writes a JSON file with the settings next to the STL.

## How to check a file

```
python tools/check_stl.py models/cube30.stl examples/cube30_uniform50.stl --porosity 50
python tools/check_stl.py models/sample.stl examples/sample_graded_z20-80.stl --graded Z 20 80
```

The input model `sample.stl` is the "Spot" cow by Keenan Crane (see `models/sources.csv`).
