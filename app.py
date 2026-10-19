"""Streamlit screen for the porous structure generator.

Run with:  streamlit run app.py
All calculation is done by porous.core.make_porous. This file only handles input and display.
"""
import tempfile
import time
from pathlib import Path

import streamlit as st

# Defaults (spec chapter 3)
DEFAULT_CELL = 6.0
DEFAULT_PITCH = 0.5
DEFAULT_SKIN = 0.0
POROSITY_MIN, POROSITY_MAX = 5, 85

try:
    from porous.core import export, load_mesh, make_porous
    ENGINE_READY = True
except ImportError:
    # The engine is not in the repository yet. Use a dummy with the same interface
    # so the screen can be built and tested first (spec chapter 4, task 4).
    ENGINE_READY = False
    import trimesh

    def load_mesh(path):
        """Dummy: load an STL and refuse it if it is not watertight."""
        mesh = trimesh.load(path, force="mesh")
        if len(mesh.faces) == 0 or not mesh.is_watertight:
            raise ValueError("Input STL is not watertight. Please repair the mesh.")
        return mesh

    def make_porous(mesh, porosity=None, graded=None, cell=6.0, pitch=0.5, skin=0.0,
                    tol=1.0, max_iter=8, progress=None):
        """Dummy: return the input mesh unchanged with an info dict in the spec format."""
        for i in range(1, 6):
            time.sleep(0.1)
            if progress:
                progress(i / 5)
        info = {"input": "", "mode": "graded" if graded else "uniform", "target": porosity,
                "graded": graded, "cell": cell, "pitch": pitch, "skin": skin, "threshold": 0.0,
                "iterations": 0, "voxel_porosity": 0.0, "mesh_porosity": 0.0,
                "watertight": bool(mesh.is_watertight), "islands_removed": 0,
                "faces": len(mesh.faces), "seconds": 0.5}
        return mesh.copy(), info

    def export(mesh, info, path):
        """Dummy: save the STL in binary format."""
        mesh.export(path, file_type="stl")


st.set_page_config(page_title="Porous Structure Generator", layout="wide")
st.title("Porous Structure Generator")
st.caption("Upload a watertight STL, choose the porosity, and download a porous STL. Units are mm.")
if not ENGINE_READY:
    st.warning("Engine not found (porous/). Running with a dummy that returns the input unchanged.")


def load_uploaded(file) -> "trimesh.Trimesh":
    """Save the uploaded STL to a temp file, pass its path to load_mesh, then delete the file.

    delete=False is needed on Windows: the file must be closed before load_mesh can open it.
    """
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
        tmp.write(file.getvalue())
    try:
        return load_mesh(tmp.name)
    finally:
        Path(tmp.name).unlink(missing_ok=True)  # Streamlit reruns often, so do not leave files behind


def mesh_to_bytes(mesh, info) -> bytes:
    """Export the mesh with the engine's export (STL + JSON) and return the STL bytes."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "porous.stl"
        export(mesh, info, path)
        return path.read_bytes()


# 1. Upload
uploaded = st.file_uploader("1. Upload an STL model", type=["stl"])
mesh = None
if uploaded is None or st.session_state.get("file_id") != uploaded.file_id:
    st.session_state.pop("result", None)  # a new file: forget the old result
    st.session_state["file_id"] = uploaded.file_id if uploaded is not None else None
if uploaded is not None:
    try:
        mesh = load_uploaded(uploaded)
        size = " x ".join(f"{e:.1f}" for e in mesh.extents)
        c1, c2, c3 = st.columns(3)
        c1.metric("Vertices", f"{len(mesh.vertices):,}")
        c2.metric("Size (mm)", size)
        c3.metric("Watertight", "Yes" if mesh.is_watertight else "No")
    except ValueError as e:
        st.error(str(e))
    except Exception as e:  # unexpected file problems
        st.error(f"Could not read this STL: {e}")

# 2. Mode
st.subheader("2. Porosity")
mode = st.radio("Mode", ["Uniform", "Graded"], horizontal=True)
if mode == "Uniform":
    porosity = st.slider("Porosity (%)", POROSITY_MIN, POROSITY_MAX, 50)
    graded = None
    target = float(porosity)
else:
    porosity = None
    g1, g2, g3 = st.columns(3)
    axis = g1.selectbox("Axis", ["Z", "X", "Y"])
    p_min = g2.slider(f"Porosity at min {axis} (%)", POROSITY_MIN, POROSITY_MAX, 20)
    p_max = g3.slider(f"Porosity at max {axis} (%)", POROSITY_MIN, POROSITY_MAX, 80)
    graded = {"axis": axis, "p_min": float(p_min), "p_max": float(p_max)}
    target = (p_min + p_max) / 2

# 3. Advanced settings
with st.expander("3. Advanced settings"):
    cell = st.number_input("Cell size (mm): size of the repeating pattern, sets the pore size",
                           min_value=1.0, max_value=50.0, value=DEFAULT_CELL, step=0.5)
    pitch = st.number_input("Voxel pitch (mm): smaller is more accurate but slower",
                            min_value=0.1, max_value=2.0, value=DEFAULT_PITCH, step=0.1)
    skin = st.number_input("Solid skin thickness (mm): 0 = no skin",
                           min_value=0.0, max_value=5.0, value=DEFAULT_SKIN, step=0.2)

# 4. Generate
if st.button("4. Generate", type="primary", disabled=mesh is None):
    bar = st.progress(0.0, text="Generating...")
    try:
        out, info = make_porous(mesh, porosity=porosity, graded=graded, cell=cell, pitch=pitch,
                                skin=skin, progress=bar.progress)
        info["input"] = uploaded.name  # keep the original file name in the JSON, not the temp file name
        # Keep the result so it survives the rerun when the download button is pressed
        st.session_state["result"] = {"info": info, "target": target,
                                      "stl": mesh_to_bytes(out, info),
                                      "name": Path(uploaded.name).stem + "_porous.stl"}
        bar.progress(1.0, text="Done")
    except ValueError as e:
        bar.empty()
        st.error(str(e))
        st.session_state.pop("result", None)

# 5. Result and 6. Download
res = st.session_state.get("result")
if res and mesh is not None:
    info = res["info"]
    st.subheader("5. Result")
    r1, r2, r3, r4, r5 = st.columns(5)
    r1.metric("Measured porosity", f"{info['mesh_porosity']:.1f}%")
    r2.metric("Error", f"{info['mesh_porosity'] - res['target']:+.1f} pt")
    r3.metric("Watertight", "Yes" if info["watertight"] else "No")
    r4.metric("Triangles", f"{info['faces']:,}")
    r5.metric("Time", f"{info['seconds']:.1f} s")
    if info.get("reached_limit"):
        st.warning("The target could not be reached exactly. The closest result is shown.")
    st.download_button("6. Download STL", data=res["stl"], file_name=res["name"], mime="model/stl")
    st.info("Check the STL in PrusaSlicer before printing. High porosity makes thin walls.")
