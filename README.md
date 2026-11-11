# Capytaine Motion Analysis

This project turns a surface-panel OBJ hull into frequency-domain hydrodynamic results and Response Amplitude Operator (RAO) plots using Capytaine 2.3.1.

The matching upstream source is checked out at `capytaine-source` (official tag `v2.3.1`). The isolated `.venv` also includes Meshio, Matplotlib, Xarray, Pandas, SciPy, NetCDF4, Joblib, JupyterLab, VTK, Gmsh, and pygmsh.

## Quick check

From a Windows terminal in this folder:

```bat
.venv\Scripts\python.exe verify_install.py
run_demo.bat
```

The demo creates a small OBJ barge, solves a coarse test case, and writes plots and tables to `outputs\demo`.

## Dashboard

Double-click `start_dashboard.bat` to open the local input dashboard. It lets you attach an OBJ, define vessel, environment, wave, DOF, damping and mooring values, run Capytaine, inspect RAO magnitude/phase plots, and download the generated files. All rotations use the centre of gravity; there is no separate rotation-centre field.

The live local release is installed at `D:\Motion Analysis` and opens at `http://127.0.0.1:8765`. The Desktop folder `Motion Analysis Website` contains separate controls to open, reload, or stop the website. The authoritative completed/remaining feature record and token-efficient skill map are in `PROJECT.md`.

When an OBJ is attached, the first dashboard step displays the actual mesh with its global X/Y/Z axes and waterline. Use drag, wheel zoom, double-click reset, or the standard-view buttons to check orientation and offsets before continuing. The right panel on this step is reserved for mesh inspection and does not show wave or environment inputs.

## Run your hull

1. Copy your mesh to `meshes\hull.obj`.
2. Copy `config.example.yaml` to `config.yaml`.
3. Edit the geometry, mass/inertia, environment, periods, headings, damping, and mooring parameters.
4. Run:

```bat
run_analysis.bat config.yaml
```

The OBJ must be a panelized hull surface made of triangles or quadrilaterals. Use metres, or set `mesh.scale_to_m`. Set the mean free surface to `z=0` (or configure its z value), with z positive upward. Face normals should point out of the body; mesh healing is enabled by default.

## Main outputs

- `hydrodynamics_and_rao.nc`: complete labelled Xarray/NetCDF dataset.
- `added_mass.csv` and `radiation_damping.csv`: radiation coefficients.
- `Froude_Krylov_force.csv`, `diffraction_force.csv`, and `excitation_force.csv`.
- `rao.csv`: complex motion response, magnitude, and phase.
- `rao_magnitude.png` and `rao_phase.png`: plots by degree of freedom and heading.
- `immersed_mesh.png`: the actual clipped mesh used by the BEM solver.
- `summary.json`: mesh, physical assumptions, and hydrostatics.

Translational RAO magnitudes are plotted in m/m. Rotational RAOs are computed in rad/m and plotted in deg/m. Phases follow Capytaine's `exp(-i omega t)` convention.

## Inputs that control RAO accuracy

For a useful engineering result, provide the real center of gravity, mass, and 6x6 rigid-body inertia matrix. The automatic fallback assumes equilibrium and a homogeneous body volume; it is suitable for workflow checks, not final vessel predictions. The dashboard accepts a target total Roll damping as a percentage of critical damping (enter `5` for 5%) and diagonal mooring stiffness when relevant.

Run a mesh-convergence study before relying on the coefficients: refine the panels, especially near the waterline and geometric curvature, and check that results stop changing materially.

## What Capytaine can calculate

The installed solver supports added mass, radiation damping, diffraction and Froude-Krylov forces, total excitation force, hydrostatics, impedance, RAOs, pressure/potential/velocity fields, free-surface elevation, Kochin functions, multi-body problems, and NetCDF/Nemoh/WAMIT-style exports. This starter workflow exports the most common seakeeping quantities and can be extended to the field outputs when needed.
