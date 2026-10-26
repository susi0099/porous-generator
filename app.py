"""Streamlit screen for the porous structure generator.

Run with:  streamlit run app.py
All calculation is done by porous.core.make_porous. This file only handles input and display.
"""
import html
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
                "graded": graded, "cell": cell, "pitch": pitch, "skin": skin,
                "threshold_initial": None, "threshold": None, "iterations": 0,
                "voxel_porosity": 0.0, "mesh_porosity": 0.0, "band_max_error": None,
                "watertight": bool(mesh.is_watertight), "islands_removed": 0,
                "faces": len(mesh.faces), "seconds": 0.5}
        return mesh.copy(), info

    def export(mesh, info, path):
        """Dummy: save the STL in binary format."""
        mesh.export(path, file_type="stl")


st.set_page_config(page_title="Porous STL Generator", layout="wide")

# Thin label/value tables. Colours follow the theme in .streamlit/config.toml.
st.markdown("""
<style>
table.kv {width:100%; border-collapse:collapse; margin-bottom:1rem; border:none !important}
table.kv tr, table.kv td {border:none !important; background:transparent !important}
table.kv td {padding:0.55rem 0 !important; border-bottom:1px solid rgba(49,51,63,0.15) !important}
table.kv td.v {text-align:right; font-variant-numeric:tabular-nums}
table.kv.small td {padding:0.35rem 0.4rem !important; font-size:0.85rem}
table.kv.small td.k {opacity:0.7}
</style>
""", unsafe_allow_html=True)


def kv_table(rows, small=False) -> str:
    """Return an HTML table of (label, value) rows."""
    cls = "kv small" if small else "kv"
    body = "".join(f"<tr><td class='k'>{html.escape(str(k))}</td><td class='v'>{v}</td></tr>"
                   for k, v in rows)
    return f"<table class='{cls}'>{body}</table>"


def signed(x: float, unit: str) -> str:
    """Format a signed number with a real minus sign, e.g. −0.9 pt."""
    return f"{x:+.1f} {unit}".replace("-", "−")


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


def settings_text(info) -> str:
    """One line describing the settings the result was made with."""
    g = info.get("graded")
    if g:
        a = g["axis"]
        mode = f"graded along {a}, {g['p_min']:g} % at min {a} to {g['p_max']:g} % at max {a}"
    else:
        mode = "uniform"
    return (f"Settings used: {mode}, cell {info['cell']:.1f} mm, pitch {info['pitch']:.1f} mm, "
            f"skin {info['skin']:.1f} mm")


# ---------------- Sidebar: all inputs ----------------
mesh = None
with st.sidebar:
    st.subheader("Model")
    uploaded = st.file_uploader("STL file", type=["stl"], label_visibility="collapsed")
    if uploaded is None or st.session_state.get("file_id") != uploaded.file_id:
        st.session_state.pop("result", None)  # a new file: forget the old result
        st.session_state["file_id"] = uploaded.file_id if uploaded is not None else None
    if uploaded is not None:
        try:
            mesh = load_uploaded(uploaded)
            size = " × ".join(f"{e:.1f}" for e in mesh.extents) + " mm"
            st.markdown(kv_table([
                ("Size", size),
                ("Volume", f"{mesh.volume:,.0f} mm³"),
                ("Triangles", f"{len(mesh.faces):,}"),
                ("Closed mesh", "Yes" if mesh.is_watertight else "No"),
            ], small=True), unsafe_allow_html=True)
        except ValueError as e:
            st.error(str(e))
        except Exception as e:  # unexpected file problems
            st.error(f"Could not read this STL: {e}")

    st.subheader("Porosity")
    mode = st.radio("Mode", ["Uniform", "Graded"], horizontal=True, label_visibility="collapsed")
    if mode == "Uniform":
        porosity = st.slider("Target (%)", POROSITY_MIN, POROSITY_MAX, 50)
        graded = None
    else:
        porosity = None
        axis = st.selectbox("Axis", ["Z", "X", "Y"])
        p_min = st.slider(f"At min {axis} (%)", POROSITY_MIN, POROSITY_MAX, 20)
        p_max = st.slider(f"At max {axis} (%)", POROSITY_MIN, POROSITY_MAX, 80)
        graded = {"axis": axis, "p_min": float(p_min), "p_max": float(p_max)}

    with st.expander("Advanced", expanded=False):
        cell = st.number_input("Cell size (mm)", min_value=1.0, max_value=50.0,
                               value=DEFAULT_CELL, step=0.5,
                               help="Length of one repeat of the pattern. Bigger cell = bigger pores.")
        pitch = st.number_input("Voxel pitch (mm)", min_value=0.1, max_value=2.0,
                                value=DEFAULT_PITCH, step=0.1,
                                help="Smaller is more accurate but slower and makes bigger files.")
        skin = st.number_input("Skin (mm)", min_value=0.0, max_value=5.0,
                               value=DEFAULT_SKIN, step=0.1,
                               help="Solid outer wall with no pores. 0 = no skin.")

    generate = st.button("Generate", type="primary", disabled=mesh is None, use_container_width=True)

# ---------------- Main area: results ----------------
st.title("Porous STL Generator")
st.caption("Gyroid lattice inside a closed STL. Units: mm.")
if not ENGINE_READY:
    st.warning("Engine not found (porous/). Running with a dummy that returns the input unchanged.")

if generate:
    bar = st.progress(0.0, text="Generating...")
    try:
        out, info = make_porous(mesh, porosity=porosity, graded=graded, cell=cell, pitch=pitch,
                                skin=skin, progress=bar.progress)
        info["input"] = uploaded.name  # keep the original file name in the JSON, not the temp file name
        stl = mesh_to_bytes(out, info)
        # Keep the result so it survives the rerun when the download button is pressed
        st.session_state["result"] = {"info": info, "stl": stl, "out_volume": float(out.volume),
                                      "name": Path(uploaded.name).stem + "_porous.stl"}
        bar.empty()
    except ValueError as e:
        bar.empty()
        st.error(str(e))
        st.session_state.pop("result", None)

res = st.session_state.get("result")
if res and mesh is not None:
    info = res["info"]
    is_graded = info.get("graded") is not None
    target = info.get("target")
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.subheader("Porosity check")
        rows = [("Target (volume-weighted)" if is_graded else "Target",
                 f"{target:.1f} %" if target is not None else "-"),
                ("Measured on the output mesh", f"{info['mesh_porosity']:.1f} %"),
                ("Error", signed(info["mesh_porosity"] - target, "pt") if target is not None else "-")]
        if is_graded:
            band = info.get("band_max_error")
            rows.append(("Largest band error (5 bands)", f"{band:.1f} pt" if band is not None else "-"))
        rows += [("Voxel estimate", f"{info['voxel_porosity']:.1f} %"),
                 ("Calibration runs", f"{info['iterations']}")]
        st.markdown(kv_table(rows), unsafe_allow_html=True)

    with right:
        st.subheader("Output file")
        st.markdown(kv_table([
            ("Closed mesh", "Yes" if info["watertight"] else "No"),
            ("Volume", f"{res['out_volume']:,.0f} mm³"),
            ("Triangles", f"{info['faces']:,}"),
            ("File size", f"{len(res['stl']) / 1e6:.1f} MB"),
            ("Time", f"{info['seconds']:.1f} s"),
        ]), unsafe_allow_html=True)
        st.download_button(f"Download {res['name']}", data=res["stl"], file_name=res["name"],
                           mime="model/stl", use_container_width=True)

    if info.get("reached_limit"):
        st.warning("The target could not be reached exactly. The closest result is shown. "
                   "Try a thinner skin or a lower porosity.")
    st.caption(settings_text(info))
    st.caption("Check the file in your slicer before printing. At high porosity the walls get thin.")
