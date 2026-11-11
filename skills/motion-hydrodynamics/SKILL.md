---
name: motion-hydrodynamics
description: Work on the Motion Analysis Capytaine workflow, including OBJ inspection, vessel properties, hydrostatics, wave periods/headings, DOFs, Roll damping, mooring stiffness, solver jobs, RAOs, and hydrodynamic outputs. Use for requests mentioning mesh, hull, axes, Capytaine, Nemoh, RAO generation, damping, mooring, radiation, diffraction, or solver failures.
---

# Motion Hydrodynamics

Use `C:\Users\HAIER\Documents\Capyteine_Motion_analysis` as the editable source root.

## Load only the relevant surface

- Solver: `run_hydrodynamics.py`
- Configuration: `config.example.yaml` and `dashboard/src/constants.js`
- API/job runner: hydrodynamic routes in `dashboard/backend.py`
- UI shell: `dashboard/src/components/HydrodynamicsWorkspace.jsx`
- Step UI: `SetupSteps.jsx`, `MeshViewer.jsx`, `SummaryRail.jsx`, `ResultsPanel.jsx`
- CLI helpers: `run_analysis.bat`, `run_demo.bat`, `verify_install.py`
- Read `README.md` for conventions and outputs.

Do not inspect sea-state or response internals unless an RAO handoff changes.

## Workflow

1. Reproduce the requested mesh, input, solver, or result issue with the smallest relevant case.
2. Preserve axes: X forward, Y port, Z upward; free surface normally at Z=0.
3. Preserve rotations about centre of gravity; do not reintroduce a rotation-centre input.
4. Treat Roll damping as percent critical in the current model; distinguish it from per-DOF mooring stiffness.
5. Add a targeted validation or regression test before changing solver semantics.
6. Build/test only Hydrodynamics for UI-only changes.
7. Update the Hydrodynamics row in `PROJECT.md` when scope or status changes.

## Current deferred work

General 6×6 external damping, off-diagonal mooring matrices, cancellation/queue controls, job comparison, advanced field outputs, multi-body cases, and formal convergence tooling remain roadmap items.
