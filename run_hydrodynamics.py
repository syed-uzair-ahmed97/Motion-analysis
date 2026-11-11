"""Run a frequency-domain Capytaine analysis from an OBJ hull mesh."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("CAPYTAINE_CACHE_DIR", str(PROJECT_DIR / ".cache"))
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import meshio
import numpy as np
import xarray as xr
import yaml
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import capytaine as cpt
from capytaine.post_pro import rao as compute_rao


RIGID_DOFS = ["Surge", "Sway", "Heave", "Roll", "Pitch", "Yaw"]
ROTATIONAL_DOFS = {"Roll", "Pitch", "Yaw"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute hydrodynamic coefficients, excitation forces, and RAOs from an OBJ hull."
    )
    parser.add_argument("config", type=Path, help="YAML analysis configuration file")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError("The YAML root must be a mapping.")
    config["_config_path"] = path
    return config


def require_vector(value: Any, name: str) -> np.ndarray:
    vector = np.asarray(value, dtype=float)
    if vector.shape != (3,):
        raise ValueError(f"{name} must contain exactly three numbers [x, y, z].")
    return vector


def require_matrix(value: Any, size: int, name: str) -> np.ndarray:
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != (size, size):
        raise ValueError(f"{name} must be a {size} x {size} matrix.")
    return matrix


def load_obj_mesh(config: dict[str, Any]) -> cpt.Mesh:
    mesh_config = config["mesh"]
    config_dir = config["_config_path"].parent
    mesh_path = Path(mesh_config["path"])
    if not mesh_path.is_absolute():
        mesh_path = (config_dir / mesh_path).resolve()
    if not mesh_path.is_file():
        raise FileNotFoundError(
            f"Hull mesh not found: {mesh_path}\n"
            "Copy the OBJ into the meshes folder and update mesh.path in the YAML file."
        )
    if mesh_path.suffix.lower() != ".obj":
        raise ValueError(f"This workflow expects an OBJ mesh, received: {mesh_path.suffix}")

    imported = meshio.read(mesh_path)
    mesh = cpt.load_mesh(imported, name=config.get("project", {}).get("name", mesh_path.stem))

    scale = float(mesh_config.get("scale_to_m", 1.0))
    if scale <= 0.0:
        raise ValueError("mesh.scale_to_m must be greater than zero.")
    mesh.vertices = mesh.vertices * scale

    translation = require_vector(mesh_config.get("translation_m", [0.0, 0.0, 0.0]), "mesh.translation_m")
    mesh.translate(translation)

    if mesh_config.get("flip_normals", False):
        mesh.flip_normals()

    if mesh_config.get("heal", True):
        mesh.heal_mesh(closed_mesh=bool(mesh_config.get("closed_mesh", True)), inplace=True)

    free_surface = float(config.get("environment", {}).get("free_surface_z_m", 0.0))
    z_min = float(mesh.vertices[:, 2].min())
    z_max = float(mesh.vertices[:, 2].max())
    if z_min >= free_surface:
        raise ValueError(
            f"The entire mesh is above the free surface (z_min={z_min:g}, free surface={free_surface:g})."
        )
    if z_max < free_surface:
        print("Note: the OBJ is entirely submerged; waterplane hydrostatics may be zero.")

    bbox = np.asarray(mesh.axis_aligned_bbox, dtype=float).reshape(3, 2)
    print(
        f"Loaded {mesh_path.name}: {mesh.nb_vertices} vertices, {mesh.nb_faces} panels, "
        f"bounds x={bbox[0].tolist()}, y={bbox[1].tolist()}, z={bbox[2].tolist()}"
    )
    return mesh


def labelled_matrix(body: cpt.FloatingBody, values: np.ndarray, name: str) -> xr.DataArray:
    matrix = body.add_dofs_labels_to_matrix(values)
    matrix.name = name
    return matrix


def build_body(config: dict[str, Any], mesh: cpt.Mesh) -> tuple[cpt.FloatingBody, dict[str, Any]]:
    body_config = config["body"]
    environment = config.get("environment", {})
    rho = float(environment.get("water_density_kg_m3", 1025.0))
    gravity = float(environment.get("gravity_m_s2", 9.81))
    free_surface = float(environment.get("free_surface_z_m", 0.0))
    center_of_mass = require_vector(body_config["center_of_mass_m"], "body.center_of_mass_m")
    rotation_center = require_vector(
        body_config.get("rotation_center_m", center_of_mass), "body.rotation_center_m"
    )
    mass = body_config.get("mass_kg")
    mass = None if mass is None else float(mass)

    lid_mesh = None
    lid_config = config.get("mesh", {}).get("lid", {})
    if lid_config.get("enabled", False):
        lid_radius = lid_config.get("faces_max_radius_m")
        lid_mesh = mesh.generate_lid(
            z=free_surface,
            faces_max_radius=None if lid_radius is None else float(lid_radius),
            name=f"{mesh.name}_lid",
        )

    body = cpt.FloatingBody(
        mesh=mesh,
        lid_mesh=lid_mesh,
        dofs=cpt.rigid_body_dofs(rotation_center=rotation_center),
        mass=mass,
        center_of_mass=center_of_mass,
        name=config.get("project", {}).get("name", mesh.name),
    )

    inertia_values = body_config.get("inertia_matrix_6x6")
    if inertia_values is None:
        body.inertia_matrix = body.compute_rigid_body_inertia(rho=rho)
        inertia_source = "homogeneous geometry approximation"
    else:
        body.inertia_matrix = labelled_matrix(
            body, require_matrix(inertia_values, 6, "body.inertia_matrix_6x6"), "inertia_matrix"
        )
        inertia_source = "user-supplied 6x6 matrix"

    immersed_for_hydrostatics = body.immersed_part(free_surface=free_surface)
    hydrostatic_values = body_config.get("hydrostatic_stiffness_6x6")
    if hydrostatic_values is None:
        body.hydrostatic_stiffness = immersed_for_hydrostatics.compute_hydrostatic_stiffness(
            rho=rho, g=gravity
        )
        stiffness_source = "computed from immersed hull"
    else:
        body.hydrostatic_stiffness = labelled_matrix(
            body,
            require_matrix(hydrostatic_values, 6, "body.hydrostatic_stiffness_6x6"),
            "hydrostatic_stiffness",
        )
        stiffness_source = "user-supplied 6x6 matrix"

    active_dofs = config.get("analysis", {}).get("degrees_of_freedom", RIGID_DOFS)
    unknown_dofs = sorted(set(active_dofs) - set(RIGID_DOFS))
    if unknown_dofs:
        raise ValueError(f"Unknown degrees of freedom: {unknown_dofs}")
    if not active_dofs:
        raise ValueError("analysis.degrees_of_freedom cannot be empty.")
    body.keep_only_dofs(active_dofs)
    body = body.immersed_part(free_surface=free_surface)
    if body.mesh.nb_faces == 0:
        raise ValueError("No immersed panels remain after clipping at the free surface.")

    assumptions = {
        "mass_kg": float(body.mass) if body.mass is not None else float(body.disp_mass(rho=rho)),
        "mass_source": "user-supplied" if mass is not None else "displaced-water equilibrium",
        "inertia_source": inertia_source,
        "hydrostatic_stiffness_source": stiffness_source,
        "active_dofs": list(body.dofs),
    }
    return body, assumptions


def diagonal_matrix(
    body: cpt.FloatingBody, values: dict[str, Any] | None, name: str
) -> xr.DataArray | None:
    if not values:
        return None
    unknown = sorted(set(values) - set(body.dofs))
    if unknown:
        raise ValueError(f"{name} contains inactive or unknown DOFs: {unknown}")
    diagonal = np.array([float(values.get(dof, 0.0)) for dof in body.dofs], dtype=float)
    return labelled_matrix(body, np.diag(diagonal), name)


def matrix_diagonal_value(matrix: xr.DataArray | None, dof: str) -> float:
    if matrix is None:
        return 0.0
    return float(matrix.sel(influenced_dof=dof, radiating_dof=dof))


def damping_with_roll_extra(
    body: cpt.FloatingBody,
    base_damping: xr.DataArray | None,
    extra_roll_damping: float,
) -> xr.DataArray:
    if base_damping is None:
        damping = labelled_matrix(body, np.zeros((len(body.dofs), len(body.dofs))), "external_damping")
    else:
        damping = base_damping.copy(deep=True)
    base_roll = matrix_diagonal_value(base_damping, "Roll")
    damping.loc[dict(influenced_dof="Roll", radiating_dof="Roll")] = base_roll + extra_roll_damping
    return damping


def roll_peak_omega_index(rao: xr.DataArray) -> int:
    roll_amplitude = np.abs(rao.sel(radiating_dof="Roll"))
    other_dimensions = [dimension for dimension in roll_amplitude.dims if dimension != "omega"]
    if other_dimensions:
        roll_amplitude = roll_amplitude.max(dim=other_dimensions)
    return int(roll_amplitude.argmax(dim="omega").item())


def apply_roll_damping_target(
    dataset: xr.Dataset,
    body: cpt.FloatingBody,
    base_damping: xr.DataArray | None,
    stiffness: xr.DataArray | None,
    target_percent: float,
) -> tuple[xr.DataArray, xr.DataArray | None, dict[str, Any] | None]:
    if target_percent <= 0.0:
        return compute_rao(dataset, dissipation=base_damping, stiffness=stiffness), base_damping, None
    if "Roll" not in body.dofs:
        raise ValueError("A positive roll damping target requires Roll to be an active degree of freedom.")

    inertia = float(dataset["inertia_matrix"].sel(influenced_dof="Roll", radiating_dof="Roll"))
    restoring = float(dataset["hydrostatic_stiffness"].sel(influenced_dof="Roll", radiating_dof="Roll"))
    restoring += matrix_diagonal_value(stiffness, "Roll")
    base_roll_damping = matrix_diagonal_value(base_damping, "Roll")
    target_ratio = target_percent / 100.0
    extra = 0.0
    reference_index = 0

    for _ in range(12):
        candidate_damping = damping_with_roll_extra(body, base_damping, extra)
        candidate_rao = compute_rao(dataset, dissipation=candidate_damping, stiffness=stiffness)
        reference_index = roll_peak_omega_index(candidate_rao)
        added_mass = float(
            dataset["added_mass"].sel(influenced_dof="Roll", radiating_dof="Roll").isel(omega=reference_index)
        )
        radiation_damping = float(
            dataset["radiation_damping"].sel(influenced_dof="Roll", radiating_dof="Roll").isel(omega=reference_index)
        )
        critical_argument = (inertia + added_mass) * restoring
        if critical_argument <= 0.0:
            period = float(dataset["period"].isel(omega=reference_index))
            raise ValueError(
                "Roll critical damping is undefined at the peak-response period "
                f"({period:g} s): (M44 + A44) * (K44 + Kext44) must be positive."
            )
        critical_damping = 2.0 * np.sqrt(critical_argument)
        updated_extra = max(0.0, target_ratio * critical_damping - radiation_damping - base_roll_damping)
        if np.isclose(updated_extra, extra, rtol=1e-7, atol=1e-9):
            extra = updated_extra
            break
        extra = updated_extra

    final_damping = damping_with_roll_extra(body, base_damping, extra)
    final_rao = compute_rao(dataset, dissipation=final_damping, stiffness=stiffness)
    reference_index = roll_peak_omega_index(final_rao)

    added_mass_curve = dataset["added_mass"].sel(influenced_dof="Roll", radiating_dof="Roll")
    radiation_curve = dataset["radiation_damping"].sel(influenced_dof="Roll", radiating_dof="Roll")
    critical_argument_curve = (inertia + added_mass_curve) * restoring
    critical_curve = 2.0 * np.sqrt(critical_argument_curve.where(critical_argument_curve > 0.0))
    percent_curve = 100.0 * (radiation_curve + base_roll_damping + extra) / critical_curve
    percent_curve.name = "roll_damping_percent_critical"
    percent_curve.attrs.update({"long_name": "Total roll damping as percentage of critical", "units": "%"})
    dataset[percent_curve.name] = percent_curve
    dataset["roll_damping_target_percent"] = xr.DataArray(
        target_percent,
        attrs={"long_name": "Target roll damping percentage of critical", "units": "%"},
    )
    dataset["extra_roll_damping"] = xr.DataArray(
        extra,
        attrs={"long_name": "Constant extra roll damping added to meet target", "units": "N*m*s/rad"},
    )

    achieved_percent = float(percent_curve.isel(omega=reference_index))
    information = {
        "target_percent_critical": target_percent,
        "achieved_percent_at_peak": achieved_percent,
        "reference_wave_period_s": float(dataset["period"].isel(omega=reference_index)),
        "extra_roll_damping_n_m_s_per_rad": extra,
    }
    print(
        "Roll damping target: "
        f"{target_percent:g}% critical; added {extra:g} N*m*s/rad; "
        f"peak-response period {information['reference_wave_period_s']:g} s; "
        f"achieved {achieved_percent:g}%."
    )
    return final_rao, final_damping, information


def build_test_matrix(config: dict[str, Any], body: cpt.FloatingBody) -> xr.Dataset:
    analysis = config["analysis"]
    period_config = analysis["wave_period_s"]
    periods = np.linspace(
        float(period_config["min"]),
        float(period_config["max"]),
        int(period_config["count"]),
    )
    if np.any(periods <= 0.0):
        raise ValueError("All wave periods must be positive.")
    omega = 2.0 * np.pi / periods
    headings_deg = np.asarray(analysis.get("wave_headings_deg", [0.0]), dtype=float)
    headings_rad = np.deg2rad(headings_deg)

    environment = config.get("environment", {})
    water_depth = environment.get("water_depth_m")
    water_depth = np.inf if water_depth is None else float(water_depth)
    return xr.Dataset(
        coords={
            "omega": omega,
            "wave_direction": headings_rad,
            "radiating_dof": list(body.dofs),
            "rho": float(environment.get("water_density_kg_m3", 1025.0)),
            "water_depth": water_depth,
        }
    )


def export_data_array(array: xr.DataArray, path: Path) -> None:
    frame = array.to_dataframe(name="value").reset_index()
    values = frame.pop("value").to_numpy()
    if np.iscomplexobj(values):
        frame["real"] = np.real(values)
        frame["imag"] = np.imag(values)
        frame["magnitude"] = np.abs(values)
        frame["phase_deg"] = np.angle(values, deg=True)
    else:
        frame["value"] = values
    frame.to_csv(path, index=False)


def plot_mesh(body: cpt.FloatingBody, path: Path, free_surface: float) -> None:
    vertices = body.mesh.vertices
    polygons = vertices[body.mesh.faces]
    figure = plt.figure(figsize=(10, 7))
    axis = figure.add_subplot(111, projection="3d")
    collection = Poly3DCollection(polygons, alpha=0.72, facecolor="#4a90a4", edgecolor="#183642")
    collection.set_linewidth(0.2)
    axis.add_collection3d(collection)
    mins = vertices.min(axis=0)
    maxs = vertices.max(axis=0)
    center = (mins + maxs) / 2.0
    radius = max(float((maxs - mins).max()) / 2.0, 1e-6)
    axis.set_xlim(center[0] - radius, center[0] + radius)
    axis.set_ylim(center[1] - radius, center[1] + radius)
    axis.set_zlim(center[2] - radius, center[2] + radius)
    axis.set_xlabel("x [m]")
    axis.set_ylabel("y [m]")
    axis.set_zlabel("z [m]")
    axis.set_title(f"Immersed mesh ({body.mesh.nb_faces} panels), free surface z={free_surface:g} m")
    axis.set_box_aspect((1, 1, 1))
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def plot_rao(rao: xr.DataArray, headings_deg: list[float], output_dir: Path) -> None:
    dofs = [str(dof) for dof in rao.coords["radiating_dof"].values]
    period = 2.0 * np.pi / np.asarray(rao.coords["omega"].values)
    order = np.argsort(period)
    columns = min(3, len(dofs))
    rows = int(np.ceil(len(dofs) / columns))

    for kind in ("magnitude", "phase"):
        figure, axes = plt.subplots(rows, columns, figsize=(5 * columns, 4.2 * rows), sharex=True)
        axes = np.atleast_1d(axes).reshape(-1)
        for axis, dof in zip(axes, dofs):
            dof_scale = float(np.nanmax(np.abs(rao.sel(radiating_dof=dof).values)))
            # Phases of symmetry-level numerical leakage are meaningless.
            phase_threshold = max(1e-12, 1e-5 * dof_scale)
            for heading_deg in headings_deg:
                values = (
                    rao.sel(wave_direction=np.deg2rad(heading_deg), method="nearest")
                    .sel(radiating_dof=dof)
                    .squeeze(drop=True)
                    .values
                )
                values = np.asarray(values).reshape(-1)[order]
                if kind == "magnitude":
                    plotted = np.abs(values)
                    if dof in ROTATIONAL_DOFS:
                        plotted = np.rad2deg(plotted)
                    ylabel = "deg/m" if dof in ROTATIONAL_DOFS else "m/m"
                else:
                    magnitude = np.abs(values)
                    plotted = np.where(
                        magnitude < phase_threshold, np.nan, np.angle(values, deg=True)
                    )
                    ylabel = "phase [deg]"
                axis.plot(period[order], plotted, marker="o", linewidth=1.6, label=f"{heading_deg:g} deg")
            axis.set_title(dof)
            axis.set_ylabel(ylabel)
            axis.grid(True, alpha=0.3)
        for axis in axes[-columns:]:
            axis.set_xlabel("Wave period [s]")
        for axis in axes[len(dofs) :]:
            axis.set_visible(False)
        if dofs:
            axes[0].legend(title="Wave heading")
        figure.suptitle(f"Response Amplitude Operator — {kind.capitalize()}")
        figure.tight_layout()
        figure.savefig(output_dir / f"rao_{kind}.png", dpi=180)
        plt.close(figure)


def json_safe(value: Any) -> Any:
    if isinstance(value, xr.DataArray):
        return json_safe(value.values)
    if isinstance(value, np.ndarray):
        return [json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)
    return value


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    cpt.set_logging(config.get("solver", {}).get("log_level", "INFO"))
    print(f"Capytaine {cpt.__version__}")

    mesh = load_obj_mesh(config)
    body, assumptions = build_body(config, mesh)
    test_matrix = build_test_matrix(config, body)

    output_config = config.get("output", {})
    output_dir = Path(output_config.get("directory", "outputs"))
    if not output_dir.is_absolute():
        output_dir = (config["_config_path"].parent / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    solver_config = config.get("solver", {})
    solver = cpt.BEMSolver()
    dataset = solver.fill_dataset(
        test_matrix,
        body,
        n_jobs=int(solver_config.get("n_jobs", 1)),
        progress_bar=bool(solver_config.get("progress_bar", True)),
        hydrostatics=True,
        mesh=True,
        wavelength=True,
        wavenumber=True,
    )

    response_config = config.get("response", {})
    external_damping = diagonal_matrix(
        body, response_config.get("linear_damping_diagonal"), "external_damping"
    )
    mooring_stiffness = diagonal_matrix(
        body, response_config.get("mooring_stiffness_diagonal"), "mooring_stiffness"
    )
    if mooring_stiffness is not None:
        dataset["mooring_stiffness"] = mooring_stiffness

    roll_damping_target = float(response_config.get("roll_damping_target_percent", 0.0) or 0.0)
    if roll_damping_target < 0.0:
        raise ValueError("response.roll_damping_target_percent cannot be negative.")
    rao, external_damping, roll_damping_information = apply_roll_damping_target(
        dataset,
        body,
        external_damping,
        mooring_stiffness,
        roll_damping_target,
    )
    if external_damping is not None:
        dataset["external_damping"] = external_damping
    rao.name = "rao"
    dataset["rao"] = rao

    cpt.export_dataset(str(output_dir / "hydrodynamics_and_rao.nc"), dataset, format="netcdf")
    for variable in (
        "added_mass",
        "radiation_damping",
        "Froude_Krylov_force",
        "diffraction_force",
        "excitation_force",
        "inertia_matrix",
        "hydrostatic_stiffness",
        "external_damping",
        "mooring_stiffness",
        "roll_damping_percent_critical",
        "rao",
    ):
        if variable in dataset:
            export_data_array(dataset[variable], output_dir / f"{variable}.csv")

    headings_deg = [float(value) for value in config["analysis"].get("wave_headings_deg", [0.0])]
    plot_rao(rao, headings_deg, output_dir)
    plot_mesh(body, output_dir / "immersed_mesh.png", float(config.get("environment", {}).get("free_surface_z_m", 0.0)))

    hydrostatics = body.compute_hydrostatics(
        rho=float(config.get("environment", {}).get("water_density_kg_m3", 1025.0)),
        g=float(config.get("environment", {}).get("gravity_m_s2", 9.81)),
    )
    summary = {
        "software": {"capytaine": cpt.__version__, "meshio": meshio.__version__},
        "mesh": {
            "vertices": body.mesh.nb_vertices,
            "immersed_panels": body.mesh.nb_faces,
            "bounds_m": body.mesh.axis_aligned_bbox,
        },
        "assumptions": assumptions,
        "roll_damping": roll_damping_information,
        "hydrostatics": hydrostatics,
        "outputs": sorted(path.name for path in output_dir.iterdir()),
    }
    with (output_dir / "summary.json").open("w", encoding="utf-8") as stream:
        json.dump(json_safe(summary), stream, indent=2)

    print(f"Analysis complete. Results: {output_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
