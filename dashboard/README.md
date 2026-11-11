# Motion Analysis Dashboard

The dashboard is a local React interface backed by FastAPI. It uploads an OBJ, creates the YAML configuration, runs the existing `run_hydrodynamics.py` workflow, tracks the solver, and exposes the plots and data files.

From the project root, double-click `start_dashboard.bat` or run:

```bat
start_dashboard.bat
```

The application opens at `http://127.0.0.1:8765`.

## OBJ inspection

After an OBJ is attached, the Hull mesh step renders the actual file in an interactive local preview. Drag to rotate, use the mouse wheel to zoom, double-click to reset, or select Isometric, Front, Side and Top views. The red X, green Y and blue Z axes start at the OBJ global origin and follow the solver convention: X forward, Y port and Z up.

The inspection panel reports vertex/face counts, scaled dimensions and the waterline relationship. It warns when the origin is outside the mesh bounds, no vertices are immersed, the geometry is fully submerged, an axis has near-zero extent, or malformed OBJ records were skipped. The preview is performed in the browser; the OBJ is sent to the local solver only when an analysis is started.

## Damping convention

Roll damping is entered as a target percentage of critical damping. For example, enter `5` for 5%, not `0.05`. The solver adds a constant Roll damping coefficient so that radiation plus external damping reaches the target at the analysed wave period that produces the largest Roll RAO. Set the target to `0` to disable it. Roll must be an active DOF for a positive target.

Mooring stiffness is also entered per DOF: `N/m` for translations and `N·m/rad` for rotations.

All rotational DOFs use the centre of gravity. The dashboard intentionally has no separate rotation-centre input.
