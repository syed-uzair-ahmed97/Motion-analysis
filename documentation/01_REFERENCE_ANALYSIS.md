# Reference-code analysis

## Reference A — zone and ERA5 workflow

### Files inspected

- `C:\Users\HAIER\Downloads\Mainfile1_May26_31_hourly.py`
- `C:\Users\HAIER\Downloads\get_ERA5_Example.py`
- `C:\Users\HAIER\Downloads\SeaRoute_zones (1).xlsx`
- `C:\Users\HAIER\Downloads\zone_checker_template.xlsx`

### What the supplied code currently does

`Mainfile1_May26_31_hourly.py` uses `cdsapi` to request ERA5 single-level reanalysis data. It requests:

- Significant height of combined wind waves and swell (`Hs`).
- Peak wave period (`Tp`).
- Hourly samples from 26–31 May 2026.
- A geographical rectangle `[North, West, South, East] = [60, -15, 35, 15]`.
- Separate NetCDF files for `Hs` and `Tp`.

The script is an acquisition script; it does not currently build the scatter diagram.

`get_ERA5_Example.py` contains the intended long-term workflow in comments:

1. Download multiple years of ERA5 data.
2. Define a route and identify nearest ERA5 grid points.
3. Mask all grid locations belonging to the route.
4. Bin `Hs` and `Tp`.
5. Count each observation into a two-dimensional matrix.
6. Divide by the total valid sample count to create a probability matrix.

### Zone workbooks

`SeaRoute_zones (1).xlsx` contains 117 rectangular zone records with:

- Zone identifier.
- Upper and lower latitude.
- Western and eastern longitude.

Several logical zones are split into `.01` and `.02` rectangles around the antimeridian or other boundaries.

`zone_checker_template.xlsx` defines the intended point-classification contract:

- Zone table in columns A:E.
- Route point longitude and latitude in columns G:H.
- Matched zone ID in column I.
- Negative coordinates are allowed.
- If west longitude is numerically greater than east longitude, the rectangle crosses the antimeridian.

### Interpretation for the web application

The sea-state workspace must separate acquisition from analysis:

- **Acquisition** produces a CSV or NetCDF observation source.
- **Spatial selection** chooses a zone/route/grid subset.
- **Quality control** pairs `Hs` and `Tp`, removes invalid records, and reports missing samples.
- **Binning** produces count and probability matrices.
- **Selection** turns a scatter cell into a downstream sea-state range and midpoint.

The implemented application accepts already-downloaded data and optional latitude/longitude bounds. It can also select the nearest available grid cell to a requested coordinate, or generate a SeaRoute path, sample it uniformly, snap those samples to unique source-grid cells, and build a route-weighted scatter matrix. Route-distance weights are applied to counts before probability normalization. Direct CDS acquisition remains a later worker feature because it requires credentials, request splitting, retry handling, and persistent background jobs.

## Reference B — MATLAB spectral response

### Files inspected

- `finalcode1.m`
- `wave_spectrum_PM_JONSWAP.m`
- `extract_RAOs_for_heading.m`
- `importRAOExcel.m`
- `getRAOData.m`
- `RAOs.xlsx`
- `RAOs1.xlsx`

### Data contract

Both RAO workbooks contain six worksheets:

- Surge
- Sway
- Heave
- Roll
- Pitch
- Yaw

The first column is wave period in seconds. Remaining columns are wave headings. `RAOs.xlsx` contains a smaller heading set; `RAOs1.xlsx` contains headings every 15 degrees from 0 to 345 degrees.

The MATLAB importer converts period to angular frequency with `omega = 2*pi/T`, selects an exact heading, and assembles six RAO series.

### MATLAB calculation sequence

1. Define `Hs`, `Tp`, JONSWAP `gamma`, voyage duration, exceedance probability, point coordinates, heading, and speed.
2. Import RAO magnitudes for the selected heading.
3. Generate PM and JONSWAP spectra.
4. Calculate encounter frequency:

   `omega_e = omega - (U/g) * omega^2 * cos(heading)`

5. Transform the wave spectrum for encounter-frequency branches.
6. Interpolate each DOF RAO and calculate displacement and acceleration spectra.
7. Integrate spectra for RMS values and zero-crossing periods.
8. Combine DOF RMS values at the point using root-sum-square equations.
9. Estimate maxima with an extreme multiplier based on duration and exceedance probability.

### Changes made deliberately in the Python version

The supplied MATLAB workbooks contain magnitude-only RAOs. The Capytaine results contain real and imaginary RAOs, so the integrated Python application preserves complex phase.

Point acceleration is calculated from a complex transfer function before taking spectral magnitude. This preserves cross terms between translational, rotational, and gravity components. It is physically more complete than applying root-sum-square independently to already-integrated DOF RMS values.

The Python integration is performed over absolute wave frequency. Encounter frequency is used for time derivatives. This avoids numerical singularities and branch interpolation around the following-sea turning point while preserving response variance.

The original MATLAB method remains documented so results can be reconciled during validation.
