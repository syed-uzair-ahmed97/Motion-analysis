# API and data contracts

## Historical-data upload

### Source inspection

`POST /api/sea-states/inspect` accepts repeated multipart `data_files` fields before calculation. The legacy `data_file` and `tp_file` fields remain accepted. A request may contain up to 100 files. It returns:

- File role detected from variables: `hs`, `tp`, or `combined_hs_tp`.
- Actual variable names, rather than a guess based on the filename.
- Time start/end and the inclusive list of detected years.
- Latitude/longitude coverage and grid-point count when coordinates exist.
- Whether each time period is a combined file or a valid separate Hs/Tp NetCDF pair.
- Total file count, time-period count, and the complete year list.

Files are grouped by their actual time coordinates. Upload order and filenames are irrelevant. For every separate-file period, the API requires exactly one recognized Hs file and one recognized Tp file. A mismatch such as two Hs files and one Tp file is rejected with the counts for that period. Duplicate/overlapping periods, incompatible geographic grids, non-overlapping Hs/Tp dates, and mixed separate CSV/NetCDF pairs are rejected.

The 100-file limit supports up to 50 years when every year uses separate Hs and Tp files, or up to 100 yearly files when each contains both variables.

`POST /api/sea-states`

Multipart fields:

- `data_files`: repeated `.csv` or `.nc`/`.netcdf` upload field, maximum 100 files.
- `data_file` and `tp_file`: backward-compatible single-period fields.
- `payload`: JSON configuration.

Configuration:

```json
{
  "hs_bin_width": 0.5,
  "tp_bin_width": 1.0,
  "hs_variable": null,
  "tp_variable": null,
  "latitude_min": null,
  "latitude_max": null,
  "longitude_min": null,
  "longitude_max": null
}
```

CSV variable aliases:

- `Hs`: `hs`, `swh`, `significant_wave_height`, `significant_height_of_combined_wind_waves_and_swell`.
- `Tp`: `tp`, `pp1d`, `peak_wave_period`.
- Optional: `time`, `latitude`/`lat`, `longitude`/`lon`.

The NetCDF loader accepts the same aliases in data variables or coordinates and broadcasts compatible `Hs`/`Tp` arrays before flattening.

For a zone request, the selected boundary must lie entirely inside the uploaded coordinate coverage. Partial overlap is rejected rather than silently producing a scatter for only the overlapping portion.

## Nearest-location scatter

`POST /api/sea-states/location`

Uses the same multipart files as the historical-data upload. The payload adds:

```json
{
  "latitude": 49.6,
  "longitude": 1.4,
  "hs_bin_width": 0.5,
  "tp_bin_width": 1.0
}
```

The source must contain latitude and longitude coordinates. The result includes `spatial_selection.requested`, `spatial_selection.matched`, and the great-circle `distance_km` between them. ERA5-style rectilinear NetCDF grids and coordinate-bearing CSV files are supported.

## Sea-route preview

`POST /api/sea-routes`

```json
{
  "origin": [4.48, 51.92],
  "destination": [-74.04, 40.68]
}
```

Coordinates follow GeoJSON order: `[longitude, latitude]`. The endpoint uses the open-source `searoute` network and returns a GeoJSON LineString plus length in nautical miles. This route is intended for environmental sampling and visualization, not vessel navigation.

## Route-weighted scatter

`POST /api/sea-states/route`

Uses the same multipart source files. The payload adds:

```json
{
  "route_coordinates": [[4.48, 51.92], [-74.04, 40.68]],
  "sample_spacing_nm": 60,
  "max_grid_distance_km": 100,
  "weighting": "route_distance",
  "hs_bin_width": 0.5,
  "tp_bin_width": 1.0
}
```

The route is sampled at approximately uniform distance, each sample is snapped to the nearest available source-grid cell, and duplicate matches are collapsed. `route_distance` weights cells by the number of uniform route samples assigned to them; `equal_grid_cells` gives every unique matched cell equal weight. Weights are applied to histogram counts before the matrix is normalized. The result includes route coordinates, sampled coordinates, matched grid cells, weight factors, and weight percentages. Processing stops if any sample is farther from the source grid than `max_grid_distance_km`, preventing a regional dataset from silently snapping an uncovered voyage to its edge cells.

When this coverage check fails, the API returns no scatter matrix and reports the uncovered sample's nearest-grid distance and the configured allowed distance.

## Demonstration scatter

`GET /api/sea-states/demo?hs_bin_width=0.5&tp_bin_width=1.0`

Returns a deterministic synthetic historical dataset processed by the same histogram function as uploaded data.

## Scatter result

```json
{
  "job_id": "uuid",
  "source_name": "historical.csv",
  "valid_observations": 67248,
  "missing_observations": 124,
  "hs_edges": [0.0, 0.5, 1.0],
  "tp_edges": [2.0, 3.0, 4.0],
  "counts": [[12, 30], [42, 51]],
  "probabilities": [[8.89, 22.22], [31.11, 37.78]],
  "top_states": [],
  "time_start": "2016-01-01T00:00:00",
  "time_end": "2025-12-31T23:00:00"
}
```

Real upload results also contain `source_manifest`, preserving every detected file, Hs/Tp role, paired period, variable, year, date extent, and geographic coverage as calculation provenance. Valid observations from all periods are concatenated before one final count/weighted-count matrix is normalized.

Matrix rows follow ascending `Hs` bins; columns follow ascending `Tp` bins. The frontend may reverse row display so higher seas appear at the top, but selection indices remain in source order.

For route results, `weighted` is `true`, `effective_weight` reports the normalization denominator, and `counts` may contain floating-point weighted counts. Unweighted upload and point-query counts remain integers.

## Spectrum preview

`POST /api/spectrum`

```json
{
  "hs": 2.75,
  "tp": 10.5,
  "gamma": 3.3,
  "points": 600
}
```

Returns angular frequency, PM/JONSWAP density arrays, `Hm0`, `m0`, and peak frequency.

## Hydrodynamic history

`GET /api/analysis`

Returns completed and in-progress Capytaine jobs discovered from persisted status files. Response analysis uses completed jobs containing `results/rao.csv`.

## Response calculation

`POST /api/responses`

```json
{
  "rao_job_id": "uuid",
  "hs": 2.75,
  "tp": 10.5,
  "gamma": 3.3,
  "heading_deg": 90.0,
  "speed_knots": 0.0,
  "point": {"x": 120.0, "y": 0.0, "z": 0.0},
  "duration_days": 42.0,
  "exceedance_probability": 0.01
}
```

Returns:

- Requested and selected solved heading.
- Sea-state and exposure inputs.
- JONSWAP and acceleration spectra.
- DOF motion/acceleration RMS.
- Point `Ax`, `Ay`, and `Az` RMS, expected maximum, and spectral period.
- Warnings for unavailable DOFs or extrapolation bounds.
- Response job ID and download URL.

## Response package

`GET /api/responses/{response_id}/download`

ZIP contents:

- `response_summary.json`
- `spectrum.csv`
- `dof_response.csv`

## Validation and limits

- `0 < Hs <= 30 m`
- `0 < Tp <= 60 s`
- `1 <= gamma <= 10`
- `0 <= speed <= 80 kn`
- `0 < duration_days <= 3650`
- `0 < exceedance_probability < 1`
- `0 < bin widths`
- `-90 <= latitude <= 90`
- `-180 <= longitude <= 180`
- `5 <= route sample spacing <= 500 nautical miles`
- `1 <= maximum route-to-grid distance <= 1000 km`
- Uploaded source size limited by the backend.
- At least two valid paired observations are required.
