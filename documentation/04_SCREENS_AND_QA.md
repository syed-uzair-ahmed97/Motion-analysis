# Screens and visual acceptance

## Global product shell

The application uses one product-level header and one navigation row for `Overview`, `Sea states`, `Hydrodynamics`, and `Response analysis`. Hydrodynamic setup steps remain inside the Hydrodynamics workspace so the application has one clear global information hierarchy.

## Screen responsibilities

| Screen | Primary responsibility | Main user action | Output handed forward |
|---|---|---|---|
| Overview | Explain status and the three-stage workflow | Open a workspace | Navigation only |
| Sea states | Convert historical `Hs`/`Tp` into an occurrence matrix | Select a populated cell | Representative `Hs`, `Tp`, probability, and count |
| Hydrodynamics | Inspect mesh and calculate complex RAOs | Run Capytaine analysis | Completed job containing `rao.csv` |
| Response analysis | Couple JONSWAP and RAOs at an evaluation point | Calculate response | Spectra, RMS, expected maxima, JSON/CSV package |

## Fidelity ledger

The generated sea-state and response concepts are retained in `dashboard/design` and were used as the visual target.

1. The dark navy navigation, white engineering panels, teal actions, thin blue-grey borders, and compact type hierarchy are preserved.
2. Sea-state source controls, bin controls, normalization, and the build action share one clear setup band.
3. The occurrence matrix remains the main visual, with a persistent selected-state rail and ranked states below it.
4. Response inputs form one setup band, while evaluation-point coordinates, the main plot, and calculated point results occupy distinct columns.
5. Wave, motion, and acceleration plots use a common code-native scientific chart rather than decorative imagery.
6. Mobile layouts stack panels without page-level horizontal overflow; the wide heatmap and result table remain locally scrollable.

## Browser acceptance flow

The production build is accepted when this flow completes without console or page errors:

1. Load the Overview workspace.
2. Open Sea states and wait for the demonstration occurrence matrix.
3. Select a populated matrix cell and confirm the selected state and JONSWAP preview update.
4. Send the state to Response analysis.
5. Select a completed hydrodynamic RAO job and calculate response.
6. Confirm three point-acceleration results and a response-package download link.
7. Open Hydrodynamics and confirm the initial screen contains the OBJ mesh input and mesh inspection, without wave/environment controls.
8. Repeat the sea-state screen at a 390-pixel mobile viewport and confirm there is no document-level horizontal overflow.
