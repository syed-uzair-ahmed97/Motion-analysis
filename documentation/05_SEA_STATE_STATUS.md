# Sea-State Module Status

Updated: 2026-08-25

## Purpose

The Sea States module constructs an Hs–Tp probability matrix from uploaded CSV or NetCDF wave histories. Zone, nearest-location, and route analyses are deliberately separate because they answer different spatial questions.

## Completed

### Source ingestion and validation

- Accepts combined Hs/Tp files or paired Hs and Tp NetCDF files.
- Supports multi-year collections and validates period pairing, overlap, variables, grid coverage, and missing years.
- Detects common ERA5 aliases for Hs, Tp, time, latitude, and longitude.
- Preserves file, variable, period, and geographic provenance in each result.
- Applies missing/non-numeric and range validation internally without displaying those diagnostic categories on the results page.

### Zone analysis

- Accepts user-defined south, north, west, and east bounds.
- Verifies that the uploaded source covers the complete requested zone.
- Removes all grid cells outside the requested zone before building the scatter matrix.
- Combines valid records inside the zone with equal contribution and no latitude multiplier.

### Location analysis

- Accepts any requested latitude and longitude.
- Selects the nearest available ERA5 grid cell.
- Reports requested coordinates, matched coordinates, and great-circle offset.
- Uses the complete time history of the matched cell.

### Route analysis

- Generates a visualization-grade SeaRoute path between origin and destination with one optional stopover.
- Displays the route on an offline Natural Earth basemap.
- Samples the route, matches samples to ERA5 cells, rejects uncovered routes, and builds one route-exposure probability matrix.
- Reports route length, sampling interval, unique ERA5 cells, and maximum match distance.

### Scatter results and exports

- Shows a responsive Hs–Tp probability heatmap, including explicit `0%` cells.
- Allows a populated state to be selected and previewed as a JONSWAP spectrum.
- Keeps internal area/route normalization totals out of user-facing panels.
- Downloads an annotated PNG for Zone, Location, and Route scatter diagrams.
- Embeds analysis type, date period, source, valid-pair total, zone bounds or point/route coordinates in every scatter image.
- Downloads an annotated route-map PNG.
- Downloads route matched-cell data as CSV with latitude, longitude, route samples, and route percentage.
- Downloads the complete Hs–Tp matrix and provenance as CSV or JSON.
- Lists saved analyses, identifies Zone/Location/Route results, and reopens completed results without re-uploading source files.
- Uses a specific no-ocean-data message when a selected zone contains only masked ERA5 wave cells.

### Interface

- Provides independent Home, Zone, Location, Route, and Results views.
- Uses a harmonized dark analysis background shared with Hydrodynamics and Response.
- Supports desktop and narrow-screen layouts.

## Future work

1. Direct Copernicus CDS/ERA5 acquisition with credentials, request splitting, retries, quotas, and background jobs.
2. Server-side catalog access for the installed ERA5 yearly archive instead of requiring browser uploads.
3. Named-zone workbook import and reusable saved zone definitions.
4. Manual variable mapping for datasets using non-standard Hs/Tp/coordinate names.
5. User-selectable time-range and seasonal/monthly filters.
6. Extend the completed saved-analysis browser with compare, rename, and delete controls.
8. Multi-state selection and batch handoff to response analysis.
9. Directional occurrence matrices and wave-direction/spreading models.
10. Optional equal-year temporal aggregation when uploaded periods contain different numbers of valid time records.

## External or scientific blockers

- Direct Copernicus acquisition cannot run until CDS credentials and an approved dataset/request policy are configured.
- Directional occurrence cannot be calculated from Hs/Tp-only files; a recognized mean/peak wave-direction variable and binning convention are required.
- The installed D-drive ERA5 catalog needs a deliberate server-side catalog policy (allowed roots, year selection, and resource limits) before exposing large local files to a future public deployment.

## Scientific invariants to preserve

- Hs and Tp must remain paired at the same time and grid coordinate.
- Values from `Hs = 0` through the first configured bin are valid and must remain counted.
- Empty bins must remain visible as `0%`.
- Zone filtering occurs before quality control and histogram construction; outside-zone points are not reported as invalid.
- Probability matrices must normalize to 100% after the applicable spatial aggregation.
- Raw uploaded files must never be modified.
