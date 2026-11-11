---
name: motion-spectral-response
description: Work on the Motion Analysis JONSWAP and vessel-response pipeline, including complex RAO interpolation, encounter frequency, motion spectra, arbitrary-point acceleration, RMS, expected maxima, plots, and response exports. Use for requests mentioning spectrum, JONSWAP, acceleration, evaluation points, exposure, exceedance, MATLAB conversion, or response calculations.
---

# Motion Spectral Response

Use `C:\Users\HAIER\Documents\Capyteine_Motion_analysis` as the editable source root.

## Load only the relevant surface

- Calculation: `analysis/spectral_response.py`
- API/export: spectrum and response routes in `dashboard/backend.py`
- UI: `dashboard/src/components/ResponseWorkspace.jsx` and `ScientificLineChart.jsx`
- Client: response functions in `dashboard/src/api.js`
- Tests: response cases in `tests/test_environmental_analysis.py` and `tests/test_api_integration.py`
- Read `documentation/02_SCIENTIFIC_METHOD.md` for formula changes.
- Read the MATLAB section of `documentation/01_REFERENCE_ANALYSIS.md` only for MATLAB reconciliation.

Do not inspect mesh/setup screens unless the RAO data contract changes.

## Workflow

1. Identify whether the change affects spectrum, RAO interpolation, encounter frequency, point transfer, statistics, display, or export.
2. Preserve complex RAO phase and rotational units in radians internally.
3. Report nearest solved heading and missing DOFs explicitly.
4. Add numerical tests for any scientific change, including units and limiting cases.
5. Compare with the documented MATLAB method when the user requests reconciliation.
6. Build/browser-test only Response analysis for UI changes.
7. Update the Response row in `PROJECT.md` when scope or status changes.

## Current deferred work

External Excel/CSV RAO import, multiple evaluation points, all-sea-state batch response, long-term weighted statistics, directional spreading, time histories, and formal OrcaWave/MATLAB benchmarks remain roadmap items.
