# Porous Structure Generator (Python prototype)

## What it does
- Loads an STL file.
- Generates a voxel-based Gyroid porous structure.
- Supports uniform and graded porosity modes.
- Estimates achieved porosity from the voxel grid.
- Exports the result as an STL file.
- Includes an experimental option to retain a solid outer skin.

## Installation
Python 3.10 or 3.11 is recommended.

1. Extract the ZIP file.
2. Open a terminal in the extracted folder.
3. Create and activate a virtual environment (recommended).
4. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

5. Run the app:

```bash
streamlit run app.py
```

The app should open in your browser. If it does not, open the local URL shown in the terminal.

## First test
- Start with a small, watertight cube STL.
- Use voxel pitch 0.8–1.0 mm and cell size 5–8 mm.
- Generate uniform 50% porosity.
- Download the STL and open it in Cura or PrusaSlicer.
- Compare the voxel-estimated porosity with a volume measurement from your mesh software.

## Important limitations
This is a prototype for research and demonstration. It uses a voxel grid, so the result depends on resolution. Porosity is calibrated approximately on the discrete grid and may not equal the requested continuous-volume porosity exactly. Graded porosity is approximate and may vary near boundaries. The optional outer skin changes achieved porosity. Always inspect the output mesh and slicer preview before printing.

STL files do not contain reliable unit metadata; this application assumes model coordinates are in millimetres.
