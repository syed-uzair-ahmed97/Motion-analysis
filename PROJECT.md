# Motion Analysis — Project Record and Feature Map

Last reviewed: **25 August 2026**

## 1. Product objective

Build one web-based marine motion-analysis application with three connected engineering workspaces:

1. **Sea-state modelling** — turn historical `Hs` and `Tp` observations into an auditable occurrence scatter diagram.
2. **Hydrodynamics** — inspect a panelized OBJ hull and calculate radiation, diffraction, hydrostatics, and complex RAOs with Capytaine.
3. **Spectral response** — combine a selected sea state and complex RAOs to calculate motion and acceleration at user-defined vessel points.

The application uses React/Vite for the frontend, FastAPI/Python for the backend, and Capytaine 2.3.1 as the hydrodynamic solver.

## 2. Working locations

| Purpose | Location |
|---|---|
| Editable source | `C:\Users\HAIER\Documents\Capyteine_Motion_analysis` |
| Live local installation | `D:\Motion Analysis` |
| Website | `http://127.0.0.1:8765` |
| Desktop reload controls | `C:\Users\HAIER\Desktop\Motion Analysis Website` |
| Project-specific skill sources | `skills\` |
| Installed Codex skills | `C:\Users\HAIER\.codex\skills\motion-*` |

Make code changes in the C-drive source, validate them, build the frontend, and only then synchronize the release to D. Preserve all live job and result folders during synchronization.

## 3. System flow

```text
Historical Hs/Tp data
        │
        ▼
Hs–Tp count and probability matrix ── select a sea-state cell
        │
        ▼
JONSWAP spectrum Sη(ω)
        │
        ├──────────────── Capytaine complex RAOs H(ω, β)
        │                              │
        └──────────────────────────────┘
                       │
                       ▼
          DOF response spectra and RMS
                       │
                       ▼
     Point acceleration transfer functions at (x, y, z)
                       │
                       ▼
      Acceleration spectra, RMS and expected maxima
```

## 4. Work completed so far

### Foundation and local environment

- Created the dedicated project and live D-drive installation.
- Installed and verified Capytaine 2.3.1 and the Python scientific stack.
- Added CLI demo/configuration workflows and a generated demonstration barge.
- Added FastAPI/Uvicorn hosting and a production React/Vite build.
- Added local job persistence and downloadable output files.

### Sea-state modelling

- Accepts CSV and ERA5-style NetCDF sources.
- Accepts Hs and Tp in one file or separate NetCDF files.
- Inspects uploads before calculation and identifies Hs/Tp files from their variables, independent of filenames or upload order.
- Accepts up to 100 files in one analysis: 50 years of separate Hs/Tp pairs or 100 combined yearly sources.
- Groups files by actual time coordinates and validates exactly one Hs and one Tp source for every separate-file period.
- Rejects missing counterparts, duplicate variables, overlapping periods, and inconsistent grids before calculation.
- Reports detected years, dates, variables, geographic coverage, grid size, and file pairing on setup and results pages.
- Rejects separate Hs/Tp files with incompatible dates or grid coverage.
- Detects common Hs, Tp, time, latitude, and longitude aliases.
- Supports geographical bounding filters in the backend, including antimeridian handling.
- Rejects a zone request when the uploaded source covers only part of the selected boundary.
- Slices each gridded yearly source to the requested zone before loading values, then combines valid observations across all validated periods.
- Rejects non-finite and physically invalid paired observations.
- Builds exact count and probability matrices with configurable Hs/Tp bin widths.
- Reports valid/missing observations, time extent, and ranked sea states.
- Provides a responsive, clickable heatmap and passes a selected cell downstream.
- Generates an immediate JONSWAP preview for the selected state.
- Includes deterministic demonstration data for evaluating the workflow without an upload.
- Separates sea-state construction into upload, nearest-location, and sea-route workflows.
- Presents Zone, Location, and Route as independent setup pages with one shared results page; setup screens no longer show a default scatter.
- Combines valid records inside a bounded zone with equal contribution and no latitude multiplier.
- Exposes optional latitude/longitude bounds for uploaded zone or regional datasets.
- Snaps requested coordinates to the nearest available ERA5-style grid cell and reports the offset distance.
- Generates visualization-grade maritime routes with the open-source SeaRoute network.
- Supports one optional stopover and displays the generated route on an offline Natural Earth world basemap.
- Samples routes uniformly, maps samples to unique source-grid cells, and supports route-distance or equal-cell weighting before probability normalization.
- Stops route analysis without producing a scatter when any route sample lies outside the configured source-grid tolerance, and reports the measured coverage gap.
- Displays the generated route and matched grid cells while keeping internal normalization factors out of the user-facing result panels.
- Exports publication-ready scatter PNGs for Zone, Location, and Route analyses with period, source, coordinates/bounds, and observation provenance embedded in the image.
- Exports an annotated route-map PNG and a route-cell CSV containing matched ERA5 coordinates, route sample counts, and route percentages.

### Hydrodynamics

- Uploads and parses panelized OBJ meshes.
- Displays the actual mesh, waterline, global origin, and X/Y/Z axes before analysis.
- Supports orbit, zoom, reset, and standard mesh views.
- Reports dimensions, vertex/face counts, immersion condition, and common mesh warnings.
- Accepts vessel mass, centre of gravity, inertia, water density/depth, wave periods/headings, and active DOFs.
- Uses centre of gravity for rotations; there is no separate rotation-centre field.
- Accepts target Roll damping as **percentage of critical damping**.
- Accepts diagonal mooring stiffness per DOF.
- Runs Capytaine radiation/diffraction cases asynchronously on the local backend.
- Exports NetCDF, added mass, radiation damping, wave forces, complex RAOs, phase/magnitude plots, immersed mesh, summary, and logs.
- Makes completed RAO jobs directly selectable by Response analysis.

### Spectral response and point acceleration

- Converted the supplied MATLAB PM/JONSWAP and response workflow to Python.
- Preserves Capytaine complex RAO phase rather than using magnitude-only response.
- Selects and reports the nearest solved circular heading.
- Calculates forward-speed encounter frequency for time derivatives.
- Produces six-DOF motion and acceleration spectra.
- Calculates `Ax`, `Ay`, and `Az` at arbitrary `(x, y, z)` coordinates.
- Reports RMS, zero-crossing period, extreme factor, and expected maximum for duration/exceedance inputs.
- Displays wave, motion, and point-acceleration plots.
- Explicitly reports unavailable RAO DOFs instead of hiding them.
- Exports response summary JSON and spectrum/DOF CSV files in a ZIP package.

### Product interface and QA

- Added Overview, Sea States, Hydrodynamics, and Response Analysis workspaces.
- Added desktop and mobile-responsive layouts.
- Removed wave/environment inputs from the initial mesh-upload view.
- Added project method/API/reference/screen documentation in `documentation\`.
- Added scientific unit tests, API tests, production builds, and browser workflow checks.

## 5. Remaining feature backlog

These items are **not implemented yet** unless later marked complete.

### A. Sea States backlog

| Feature | Status | Notes |
|---|---|---|
| Direct Copernicus/ERA5 acquisition | Missing | Needs credentials, request splitting, retry/quota handling, and background jobs. |
| Zone and route selector | Partial | Zone bounds, equal-contribution zone aggregation, route generation, optional stopover, nearest-grid mapping, and route exposure aggregation are complete; importing the supplied named-zone workbook remains. |
| Installed ERA5 2016–2025 catalog | Missing | The 20 yearly files under `D:\ERA5\wavedata\Zone` were verified, but the dashboard does not yet stream them as a server-side catalog; current real calculations start from a user-selected upload. |
| Variable-mapping UI | Missing | Backend aliases exist, but users cannot manually map unusual NetCDF/CSV variable names in the screen. |
| Spatial and time filter UI | Partial | Bounds and nearest-point selection are exposed; time-range filtering is not implemented. |
| Scatter download | Complete | Zone, Location, and Route results export annotated PNG images plus complete matrix CSV/JSON. Route results also export a map PNG and matched-cell CSV. |
| Saved scatter history UI | Partial | Users can list and reopen saved jobs and download their CSV/JSON; comparison, rename, and deletion remain. |
| Multiple selected sea states | Missing | Current workflow selects one representative cell at a time. |
| Directional occurrence model | Missing | Current scatter contains Hs and Tp only; wave direction/spreading is excluded. |

### B. Hydrodynamics backlog

| Feature | Status | Notes |
|---|---|---|
| General external damping matrix | Missing | Current percentage target applies to Roll only. |
| Full 6×6 mooring stiffness | Missing | Current UI accepts diagonal stiffness only. |
| Solver cancel/retry/queue controls | Missing | Jobs run in a local in-process thread pool. |
| Job history comparison | Missing | No side-by-side RAO or coefficient comparison screen. |
| Automated mesh-convergence study | Missing | The user must currently repeat refinements manually. |
| Advanced field outputs | Missing | Pressure/potential/velocity, free-surface elevation, Kochin functions, and similar Capytaine outputs are not exposed. |
| Multi-body hydrodynamics | Missing | Current workflow assumes one body. |

### C. Spectral Response backlog

| Feature | Status | Notes |
|---|---|---|
| External RAO import | Missing | Supplied Excel/magnitude-only RAOs are documented but the UI selects Capytaine jobs only. |
| Multiple evaluation points | Missing | Current calculation evaluates one point per request. |
| Batch response for every scatter cell | Missing | Needed for long-term operability/acceleration statistics. |
| Probability-weighted long-term response | Missing | Scatter probability is not yet accumulated into annual/route response metrics. |
| Directional spectrum/spreading | Missing | Current JONSWAP model is single-heading and unidirectional. |
| Response time histories | Missing | Version one is frequency-domain/statistical only. |
| Formal MATLAB/OrcaWave benchmark suite | Missing | Formula-level checks exist; reference-vessel acceptance tolerances still need to be agreed. |
| Plot/report export | Partial | Numeric ZIP exists; chart images and an engineering PDF report are not included. |
| Forward-speed hydrodynamic coefficients | Missing | Speed changes encounter frequency only; it does not recompute a forward-speed BEM solution. |

### D. Product and cloud backlog

| Feature | Status | Notes |
|---|---|---|
| Save/load named projects | Missing | Browser state and related jobs are not grouped into a named vessel project. |
| Persistent database | Missing | Metadata currently lives in filesystem JSON. |
| Authentication and multi-user isolation | Missing | Required before public hosting. |
| Durable object storage and backups | Missing | Required for hosted meshes and large NetCDF results. |
| Worker queue/resource limits | Missing | CPU/RAM-heavy Capytaine runs must be separated from the web API. |
| Monitoring and audit logs | Missing | Needed for production operations. |
| Public cloud deployment | Missing | The app is currently local-only. Cloudflare can host/cache the frontend, but not the long CPU-bound solver by itself. |

## 6. Recommended implementation order

1. **Scientific benchmark baseline** — agree on one hull, mesh, headings, damping, and OrcaWave/MATLAB comparison tolerances.
2. **Save/load named projects** — prevent re-entry of vessel, environment, mesh, and response settings.
3. **Zone/route ERA5 workflow** — expose spatial/time selection, then add credentialed acquisition.
4. **Batch sea-state response** — evaluate selected/all populated states and probability-weight long-term metrics.
5. **External RAO import and multiple points** — support legacy data and operational point sets.
6. **Solver job controls and cloud worker architecture** — prerequisite for reliable public hosting.
7. **Engineering report export** — package inputs, assumptions, plots, warnings, and results.

This order is a recommendation, not a restriction. The feature skills below allow any module to be changed independently.

## 7. Feature skills for token-efficient work

Use one skill name in a future request. The agent should open only that feature’s files and immediate dependencies.

| Skill | Use it for | Example request |
|---|---|---|
| `$motion-sea-states` | ERA5, Hs/Tp, zones, filters, scatter diagrams | “Use `$motion-sea-states` to add a date filter.” |
| `$motion-hydrodynamics` | OBJ, axes, Capytaine, damping, mooring, RAOs | “Use `$motion-hydrodynamics` to diagnose my mesh failure.” |
| `$motion-spectral-response` | JONSWAP, encounter, point acceleration, response export | “Use `$motion-spectral-response` to support five points.” |
| `$motion-dashboard-ui` | One screen, field, layout, button, chart, or wording change | “Use `$motion-dashboard-ui` to move the RAO selector.” |
| `$motion-local-hosting` | Reload, localhost, D-drive deployment, cloud architecture | “Use `$motion-local-hosting` to reload the website.” |

If the request names a screen but not a skill, route it to the matching skill automatically. Do not reread the entire project unless the request changes a cross-module data contract.

## 8. Key scientific boundaries

- Linear potential-flow RAOs and linear response superposition are assumed.
- The sea state is stationary and currently represented by one unidirectional JONSWAP spectrum.
- Rotational RAOs are radians per metre internally.
- Point coordinates use X forward, Y port, Z upward relative to the centre of gravity.
- Roll damping percentage is not a general six-DOF damping percentage.
- Expected maxima are statistical narrow-band estimates, not deterministic design accelerations.
- Forward speed currently modifies encounter frequency only.

Detailed formulas and contracts remain in:

- `documentation\01_REFERENCE_ANALYSIS.md`
- `documentation\02_SCIENTIFIC_METHOD.md`
- `documentation\03_API_AND_DATA_CONTRACTS.md`
- `documentation\04_SCREENS_AND_QA.md`

## 9. Known technical maintenance

- The current eight-test suite passes, but FastAPI emits a deprecation warning for its legacy `httpx` TestClient compatibility path.
- The NetCDF regression test passes, but the installed NumPy/NetCDF4 stack emits binary/deprecation warnings that should be removed by pinning and rebuilding a mutually compatible scientific environment before public production deployment.
- Local job metadata uses filesystem JSON and an in-process executor; both should be replaced for multi-user/cloud operation.
