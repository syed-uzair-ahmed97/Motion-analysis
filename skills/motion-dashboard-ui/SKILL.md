---
name: motion-dashboard-ui
description: Make targeted React/Vite interface changes to the Motion Analysis dashboard without rereading scientific modules. Use for requests about a screen, field, button, navigation, layout, responsive behavior, chart presentation, wording, accessibility, or other frontend-only behavior.
---

# Motion Dashboard UI

Use `C:\Users\HAIER\Documents\Capyteine_Motion_analysis\dashboard` as the frontend root.

## Route directly to the requested screen

- Global navigation/state: `src/App.jsx`, `src/components/ProductShell.jsx`
- Overview: `src/components/OverviewWorkspace.jsx`
- Sea states: `SeaStateWorkspace.jsx`, `ScatterHeatmap.jsx`
- Hydrodynamics: `HydrodynamicsWorkspace.jsx`, `SetupSteps.jsx`, `MeshViewer.jsx`, `SummaryRail.jsx`, `ResultsPanel.jsx`
- Response: `ResponseWorkspace.jsx`, `ScientificLineChart.jsx`
- Shared data/defaults: `src/api.js`, `src/constants.js`
- Styling: `src/styles.css`

Open only the requested component plus its immediate shared files. Do not read Python calculation code for presentation-only changes.

## Workflow

1. Preserve the existing navy/white/teal engineering design language unless redesign is requested.
2. Keep calculation units, warnings, and scientific labels explicit.
3. Use the installed frontend design/testing skills for significant visual changes.
4. Run `pnpm run build` after code changes.
5. Browser-test the changed path at desktop and 390-pixel mobile widths; check console/page errors.
6. Sync `dashboard/dist` to the live D-drive copy only after validation.
