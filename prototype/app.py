import io
import numpy as np
import streamlit as st
import trimesh
from skimage.measure import marching_cubes

st.set_page_config(page_title="Porous Structure Generator", layout="wide")
st.title("Porous Structure Generator for 3D Printing")
st.caption("Prototype: convert a watertight STL into a voxel-based porous STL using a Gyroid pattern.")

st.warning(
    "This is a research prototype. Check dimensions, mesh integrity, actual porosity, "
    "minimum wall thickness, and slicer compatibility before printing or using a part structurally."
)

def load_mesh(file_bytes):
    loaded = trimesh.load(io.BytesIO(file_bytes), file_type="stl", force="mesh")
    if isinstance(loaded, trimesh.Scene):
        meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise ValueError("No triangle mesh was found in the STL.")
        loaded = trimesh.util.concatenate(meshes)
    if not isinstance(loaded, trimesh.Trimesh) or len(loaded.faces) == 0:
        raise ValueError("The STL does not contain a valid triangle mesh.")
    loaded.remove_unreferenced_vertices()
    return loaded

def gyroid_field(x, y, z, cell_size):
    # Coordinates scaled so cell_size is approximately one repeating unit.
    k = 2.0 * np.pi / float(cell_size)
    X, Y, Z = k*x, k*y, k*z
    return np.sin(X)*np.cos(Y) + np.sin(Y)*np.cos(Z) + np.sin(Z)*np.cos(X)

def generate_porous(mesh, pitch, cell_size, mode, target_porosity,
                    p_low, p_high, axis, keep_skin, skin_mm, progress=None):
    # Voxelize and fill the original model.
    vg = mesh.voxelized(pitch).fill()
    solid = np.asarray(vg.matrix, dtype=bool)
    if solid.size == 0 or not solid.any():
        raise ValueError("Voxelization produced an empty model. Try a smaller voxel pitch.")
    shape = solid.shape
    ijk = np.indices(shape, dtype=np.float32).reshape(3, -1).T
    points = vg.indices_to_points(ijk)
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    field = gyroid_field(x, y, z, cell_size)

    # Keep only the original solid voxels. Porosity is calibrated against this discrete grid.
    if mode == "Uniform":
        desired = np.full(len(points), target_porosity / 100.0, dtype=np.float32)
    else:
        coords = {"X": x, "Y": y, "Z": z}[axis]
        cmin, cmax = float(coords.min()), float(coords.max())
        normalized = (coords - cmin) / max(cmax - cmin, 1e-12)
        desired = (p_low + (p_high - p_low) * normalized) / 100.0

    inside_values = field[solid.ravel()]
    desired_inside = desired[solid.ravel()]
    # Thresholds are calibrated on the field values inside the part. This gives approximate
    # target volume fractions on the voxel grid, not a guarantee of exact continuous porosity.
    thresholds = np.empty(len(inside_values), dtype=np.float32)
    if mode == "Uniform":
        q = np.clip(1.0 - target_porosity / 100.0, 0.01, 0.99)
        threshold = float(np.quantile(inside_values, q))
        thresholds[:] = threshold
    else:
        # Build a small calibration lookup from field quantiles; interpolate threshold by desired
        # solid fraction. Local calibration is approximate, especially near outer boundaries.
        quantiles = np.linspace(0.01, 0.99, 99)
        q_thresholds = np.quantile(inside_values, quantiles)
        # desired porosity p -> material fraction (1-p); higher threshold removes more material.
        thresholds[:] = np.interp(1.0 - desired_inside, quantiles, q_thresholds)

    porous_flat = np.zeros(solid.size, dtype=bool)
    solid_flat = solid.ravel()
    porous_flat[solid_flat] = inside_values > thresholds

    # Optional solid outer skin: retain occupied voxels close to the model exterior.
    if keep_skin and skin_mm > 0:
        try:
            from scipy.ndimage import distance_transform_edt
            distance_inside = distance_transform_edt(solid, sampling=pitch)
            skin = solid & (distance_inside <= skin_mm)
            porous_flat[skin.ravel()] = True
        except Exception as exc:
            raise RuntimeError("Could not create outer skin. Install SciPy and retry.") from exc

    porous = porous_flat.reshape(shape)
    if not porous.any():
        raise ValueError("No material remains. Reduce the porosity or use a smaller threshold.")
    if progress:
        progress(0.75)

    # Marching Cubes creates a triangle mesh from the binary voxel volume.
    verts, faces, normals, values = marching_cubes(porous.astype(np.uint8), level=0.5)
    # marching_cubes vertices are in array-index coordinates; map to model coordinates.
    verts_world = vg.indices_to_points(verts)
    out = trimesh.Trimesh(vertices=verts_world, faces=faces, process=True)
    out.remove_unreferenced_vertices()
    if progress:
        progress(1.0)

    original_voxels = int(solid.sum())
    material_voxels = int(porous.sum())
    measured_porosity = 100.0 * (1.0 - material_voxels / max(original_voxels, 1))
    return out, measured_porosity, original_voxels, material_voxels

uploaded = st.file_uploader("Upload an STL model", type=["stl"])

left, right = st.columns(2)
with left:
    mode = st.radio("Porosity mode", ["Uniform", "Graded"], horizontal=True)
    cell_size = st.number_input("Gyroid unit-cell size (same units as STL; assumed mm)", min_value=1.0, max_value=100.0, value=6.0, step=1.0)
    pitch = st.number_input("Voxel pitch / resolution (smaller = finer, slower)", min_value=0.25, max_value=5.0, value=0.8, step=0.1)
with right:
    if mode == "Uniform":
        target_porosity = st.slider("Target porosity (%)", min_value=5, max_value=85, value=50)
        p_low, p_high, axis = 20, 80, "Z"
    else:
        axis = st.selectbox("Gradient direction", ["X", "Y", "Z"])
        p_low = st.slider(f"Porosity at minimum {axis} coordinate (%)", 5, 85, 20)
        p_high = st.slider(f"Porosity at maximum {axis} coordinate (%)", 5, 85, 80)
        target_porosity = 50

    keep_skin = st.checkbox("Keep a solid outer skin (experimental)", value=False)
    skin_mm = st.number_input("Outer skin thickness (mm)", min_value=0.0, max_value=5.0, value=0.8, step=0.1, disabled=not keep_skin)

st.caption("Important: STL files do not store units. This app assumes the model coordinates and cell size are in millimetres.")

if uploaded is not None:
    try:
        mesh = load_mesh(uploaded.getvalue())
        st.success(f"Loaded mesh: {len(mesh.vertices):,} vertices, {len(mesh.faces):,} faces.")
        if not mesh.is_watertight:
            st.warning("The input mesh is not watertight. Voxelization may still work, but results can be unreliable; repair the STL in a mesh editor if needed.")
        bounds = mesh.bounds
        st.write(f"Bounding box (model units): X {bounds[0,0]:.2f}–{bounds[1,0]:.2f}, "
                 f"Y {bounds[0,1]:.2f}–{bounds[1,1]:.2f}, Z {bounds[0,2]:.2f}–{bounds[1,2]:.2f}")
        if st.button("Generate porous STL", type="primary"):
            bar = st.progress(0)
            with st.spinner("Voxelizing the model and generating the porous structure..."):
                out_mesh, actual_porosity, n_original, n_material = generate_porous(
                    mesh, float(pitch), float(cell_size), mode, float(target_porosity),
                    float(p_low), float(p_high), axis, keep_skin, float(skin_mm),
                    progress=bar.progress
                )
            st.success("Generation complete.")
            c1, c2, c3 = st.columns(3)
            c1.metric("Voxel-estimated porosity", f"{actual_porosity:.1f}%")
            c2.metric("Original occupied voxels", f"{n_original:,}")
            c3.metric("Remaining material voxels", f"{n_material:,}")
            st.caption("The displayed porosity is estimated from the voxel grid. Mesh-surface volume can differ slightly.")
            st.info("Open the exported STL in Cura, PrusaSlicer, or another slicer. Inspect thin walls and disconnected regions before printing.")
            output = io.BytesIO()
            out_mesh.export(output, file_type="stl")
            st.download_button(
                "Download porous STL",
                data=output.getvalue(),
                file_name="porous_structure.stl",
                mime="model/stl"
            )
            st.write(f"Output mesh: {len(out_mesh.vertices):,} vertices, {len(out_mesh.faces):,} faces; watertight: {out_mesh.is_watertight}")
    except Exception as e:
        st.error(f"Could not process this STL: {e}")
else:
    st.info("Upload an STL file to begin.")

with st.expander("Limitations and recommended checks"):
    st.markdown("""
- This is a first working prototype, not production-certified software.
- Porosity is approximated on a voxel grid. A 2–3 percentage-point error target must be verified with test models.
- Fine voxel pitch increases memory use and processing time. Start with a small model and pitch around 0.8–1.0 mm.
- Very small cells, thin walls, high porosity, or complex input meshes can create fragile or disconnected features.
- The optional outer skin is experimental and may change the achieved porosity.
- Before printing, inspect the STL in a slicer and verify the physical dimensions, wall thickness, and print settings.
""")
