---
name: motion-sea-states
description: Work on the Motion Analysis environmental-data pipeline, including ERA5/CSV/NetCDF import, Hs–Tp binning, zone or route filtering, occurrence matrices, sea-state selection, and scatter exports. Use for requests mentioning sea states, scatter diagrams, Hs, Tp, ERA5, zones, routes, historical waves, or environmental data.
---

# Motion Sea States

Use `C:\Users\HAIER\Documents\Capyteine_Motion_analysis` as the editable source root.

## Load only the relevant surface

- Calculation: `analysis/sea_state.py`
- API: sea-state routes in `dashboard/backend.py`
- UI: `dashboard/src/components/SeaStateWorkspace.jsx` and `ScatterHeatmap.jsx`
- Client: sea-state functions in `dashboard/src/api.js`
- Tests: sea-state cases in `tests/test_environmental_analysis.py` and `tests/test_api_integration.py`
- Read `documentation/01_REFERENCE_ANALYSIS.md` only for ERA5, zone, or route work.
- Read `documentation/03_API_AND_DATA_CONTRACTS.md` only when changing the request/response contract.

Do not inspect hydrodynamic or response code unless the selected-state handoff changes.

## Workflow

1. Confirm the requested change belongs to acquisition, filtering, binning, display, selection, or export.
2. Preserve paired Hs/Tp quality control, exact bin edges, counts, and probability normalization.
3. Keep raw uploads unchanged and surface discarded/missing counts.
4. Add focused unit/API tests for calculation or contract changes.
5. Build and browser-test only the affected screen for UI changes.
6. Update the Sea States row in `PROJECT.md` when scope or status changes.

## Current deferred work

Direct CDS/ERA5 acquisition, zone/route selection UI, time/spatial filter UI, scatter download/history, multi-state batch selection, and directional distributions remain roadmap items.
