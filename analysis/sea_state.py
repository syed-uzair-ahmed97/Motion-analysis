"""Historical wave-data parsing and Hs–Tp occurrence matrices."""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import xarray as xr


HS_ALIASES = (
    "hs",
    "swh",
    "significant_wave_height",
    "significant_height_of_combined_wind_waves_and_swell",
)
TP_ALIASES = ("tp", "pp1d", "peak_wave_period")
LAT_ALIASES = ("latitude", "lat")
LON_ALIASES = ("longitude", "lon")
TIME_ALIASES = ("time", "datetime", "date", "valid_time")


class SeaStateError(ValueError):
    """Raised when historical wave data cannot be interpreted safely."""


def _years_from_extent(start: str | None, end: str | None) -> list[int]:
    if not start or not end:
        return []
    return list(range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1))


def _source_role(names: Iterable[Any]) -> tuple[str, str | None, str | None]:
    hs_name = _optional_name(names, HS_ALIASES)
    tp_name = _optional_name(names, TP_ALIASES)
    if hs_name and tp_name:
        return "combined_hs_tp", hs_name, tp_name
    if hs_name:
        return "hs", hs_name, None
    if tp_name:
        return "tp", None, tp_name
    return "unknown", None, None


def inspect_wave_source(path: str | Path) -> dict[str, Any]:
    """Read only source metadata needed to identify variables, years, and coverage."""
    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix == ".csv":
        frame = pd.read_csv(source)
        if frame.empty:
            raise SeaStateError(f"{source.name} contains no observations")
        role, hs_name, tp_name = _source_role(frame.columns)
        lat_name = _optional_name(frame.columns, LAT_ALIASES)
        lon_name = _optional_name(frame.columns, LON_ALIASES)
        time_name = _optional_name(frame.columns, TIME_ALIASES)
        latitude = pd.to_numeric(frame[lat_name], errors="coerce").to_numpy(dtype=float) if lat_name else np.array([])
        longitude = pd.to_numeric(frame[lon_name], errors="coerce").to_numpy(dtype=float) if lon_name else np.array([])
        time_start, time_end = _time_extent(frame[time_name].to_numpy() if time_name else None)
        records = int(len(frame))
        coordinate_mask = np.isfinite(latitude) & np.isfinite(longitude) if latitude.size and longitude.size else np.array([], dtype=bool)
        grid_points = int(len(np.unique(np.column_stack((latitude[coordinate_mask], longitude[coordinate_mask])), axis=0))) if coordinate_mask.size else None
    elif suffix in {".nc", ".netcdf"}:
        with xr.open_dataset(source) as dataset:
            role, hs_name, tp_name = _source_role(dataset.data_vars)
            names = (*dataset.coords.keys(), *dataset.dims)
            lat_name = _optional_name(names, LAT_ALIASES)
            lon_name = _optional_name(names, LON_ALIASES)
            time_name = _optional_name(names, TIME_ALIASES)
            latitude = np.asarray(dataset.coords[lat_name].values, dtype=float).reshape(-1) if lat_name and lat_name in dataset.coords else np.array([])
            longitude = np.asarray(dataset.coords[lon_name].values, dtype=float).reshape(-1) if lon_name and lon_name in dataset.coords else np.array([])
            time_start, time_end = _time_extent(dataset.coords[time_name].values if time_name and time_name in dataset.coords else None)
            records = int(dataset[hs_name or tp_name].size) if hs_name or tp_name else 0
            grid_points = int(latitude.size * longitude.size) if latitude.size and longitude.size else None
    else:
        raise SeaStateError(f"{source.name} must be CSV, NC, or NetCDF")
    if role == "unknown":
        raise SeaStateError(f"{source.name} contains neither a recognized Hs nor Tp variable")
    finite_latitude = latitude[np.isfinite(latitude)]
    finite_longitude = longitude[np.isfinite(longitude)]
    return {
        "file_name": source.name,
        "format": "CSV" if suffix == ".csv" else "NetCDF",
        "role": role,
        "hs_variable": hs_name,
        "tp_variable": tp_name,
        "time_variable": time_name,
        "latitude_variable": lat_name,
        "longitude_variable": lon_name,
        "time_start": time_start,
        "time_end": time_end,
        "years": _years_from_extent(time_start, time_end),
        "records": records,
        "grid_points": grid_points,
        "coverage": {
            "latitude_min": float(np.min(finite_latitude)) if finite_latitude.size else None,
            "latitude_max": float(np.max(finite_latitude)) if finite_latitude.size else None,
            "longitude_min": float(np.min(finite_longitude)) if finite_longitude.size else None,
            "longitude_max": float(np.max(finite_longitude)) if finite_longitude.size else None,
        },
    }


def _same_coverage(reference: dict[str, Any], candidate: dict[str, Any]) -> bool:
    for key in reference:
        left, right = reference[key], candidate[key]
        if left is None or right is None:
            if left != right:
                return False
        elif not math.isclose(left, right, abs_tol=1e-6):
            return False
    return True


def inspect_wave_source_collection(paths: Iterable[str | Path], *, max_files: int = 100) -> dict[str, Any]:
    """Validate a chronological collection of combined files or separate Hs/Tp pairs."""
    candidates = [Path(path) for path in paths]
    if not candidates:
        raise SeaStateError("Select at least one Hs/Tp source file")
    if len(candidates) > max_files:
        raise SeaStateError(f"Select no more than {max_files} files per analysis")
    sources = [{**inspect_wave_source(path), "input_index": index} for index, path in enumerate(candidates)]
    if len(sources) > 1 and any(not source["years"] for source in sources):
        raise SeaStateError("Every file in a multi-file upload must contain a recognizable time coordinate")

    grouped: dict[tuple[int, ...], list[dict[str, Any]]] = {}
    for source in sources:
        key = tuple(source["years"])
        grouped.setdefault(key, []).append(source)

    groups = []
    for years, items in sorted(grouped.items()):
        combined = [item for item in items if item["role"] == "combined_hs_tp"]
        hs_files = [item for item in items if item["role"] == "hs"]
        tp_files = [item for item in items if item["role"] == "tp"]
        period = str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}" if years else "undated"
        if combined:
            if len(items) != 1:
                raise SeaStateError(f"Period {period} has duplicate or mixed sources; use one combined file or one Hs/Tp pair")
            group_items = combined
            pairing = "combined_file"
        else:
            if len(hs_files) != 1 or len(tp_files) != 1 or len(items) != 2:
                raise SeaStateError(
                    f"Period {period} has a mismatch: found {len(hs_files)} Hs file(s) and {len(tp_files)} Tp file(s). "
                    "Provide exactly one of each."
                )
            if any(item["format"] != "NetCDF" for item in items):
                raise SeaStateError(f"Period {period}: separate Hs/Tp files must both be NetCDF")
            group_items = [hs_files[0], tp_files[0]]
            pairing = "separate_hs_tp"
        starts = [item["time_start"] for item in group_items if item["time_start"]]
        ends = [item["time_end"] for item in group_items if item["time_end"]]
        time_start = max(starts) if starts else None
        time_end = min(ends) if ends else None
        if time_start and time_end and pd.Timestamp(time_start) > pd.Timestamp(time_end):
            raise SeaStateError(f"Period {period}: Hs and Tp files have no overlapping dates")
        if any(not _same_coverage(group_items[0]["coverage"], item["coverage"]) for item in group_items[1:]):
            raise SeaStateError(f"Period {period}: Hs and Tp files do not use the same geographic coverage")
        groups.append({
            "years": list(years), "pairing": pairing, "time_start": time_start, "time_end": time_end,
            "file_indices": [item["input_index"] for item in group_items],
        })

    reference = sources[0]
    for source in sources[1:]:
        if not _same_coverage(reference["coverage"], source["coverage"]) or reference["grid_points"] != source["grid_points"]:
            raise SeaStateError("All uploaded periods must use the same geographic grid coverage and grid size")
    ordered_groups = sorted(groups, key=lambda group: group["time_start"] or "")
    for previous, current in zip(ordered_groups, ordered_groups[1:]):
        if previous["time_end"] and current["time_start"] and pd.Timestamp(current["time_start"]) <= pd.Timestamp(previous["time_end"]):
            raise SeaStateError("Uploaded periods overlap in time; remove duplicate years or overlapping files")
    years = sorted({year for group in groups for year in group["years"]})
    missing_years = sorted(set(range(years[0], years[-1] + 1)) - set(years)) if years else []
    pairings = {group["pairing"] for group in groups}
    return {
        "status": "ready",
        "pairing": pairings.pop() if len(pairings) == 1 else "mixed_collection",
        "file_count": len(sources),
        "period_count": len(groups),
        "files": sources,
        "groups": ordered_groups,
        "time_start": min((group["time_start"] for group in groups if group["time_start"]), default=None),
        "time_end": max((group["time_end"] for group in groups if group["time_end"]), default=None),
        "years": years,
        "missing_years": missing_years,
        "coverage": reference["coverage"],
        "grid_points": reference["grid_points"],
    }


def inspect_wave_source_pair(paths: Iterable[str | Path]) -> dict[str, Any]:
    """Backward-compatible wrapper for source collection inspection."""
    return inspect_wave_source_collection(paths)


def resolve_wave_source_collection(paths: Iterable[str | Path]) -> tuple[list[tuple[Path, Path | None]], dict[str, Any]]:
    candidates = [Path(path) for path in paths]
    manifest = inspect_wave_source_collection(candidates)
    segments = []
    for group in manifest["groups"]:
        group_sources = [manifest["files"][index] for index in group["file_indices"]]
        if group["pairing"] == "combined_file":
            segments.append((candidates[group_sources[0]["input_index"]], None))
        else:
            by_role = {source["role"]: candidates[source["input_index"]] for source in group_sources}
            segments.append((by_role["hs"], by_role["tp"]))
    return segments, manifest


def resolve_wave_source_paths(paths: Iterable[str | Path]) -> tuple[Path, Path | None, dict[str, Any]]:
    segments, manifest = resolve_wave_source_collection(paths)
    if len(segments) != 1:
        raise SeaStateError("This operation expects one time period")
    return segments[0][0], segments[0][1], manifest


def _normalized_lookup(names: Iterable[Any]) -> dict[str, str]:
    return {str(name).strip().casefold(): str(name) for name in names}


def _find_name(names: Iterable[Any], preferred: str | None, aliases: tuple[str, ...], label: str) -> str:
    lookup = _normalized_lookup(names)
    if preferred:
        match = lookup.get(str(preferred).strip().casefold())
        if match:
            return match
        raise SeaStateError(f"Configured {label} variable '{preferred}' was not found")
    for alias in aliases:
        match = lookup.get(alias.casefold())
        if match:
            return match
    raise SeaStateError(f"Could not find {label}. Expected one of: {', '.join(aliases)}")


def _optional_name(names: Iterable[Any], aliases: tuple[str, ...]) -> str | None:
    lookup = _normalized_lookup(names)
    for alias in aliases:
        match = lookup.get(alias.casefold())
        if match:
            return match
    return None


def _finite_optional(value: Any) -> float | None:
    if value in (None, ""):
        return None
    number = float(value)
    if not math.isfinite(number):
        raise SeaStateError("Geographical filter values must be finite")
    return number


def _coordinate_mask(latitude: np.ndarray | None, longitude: np.ndarray | None, config: dict[str, Any]) -> np.ndarray | None:
    lat_min = _finite_optional(config.get("latitude_min"))
    lat_max = _finite_optional(config.get("latitude_max"))
    lon_min = _finite_optional(config.get("longitude_min"))
    lon_max = _finite_optional(config.get("longitude_max"))
    if all(value is None for value in (lat_min, lat_max, lon_min, lon_max)):
        return None
    if latitude is None or longitude is None:
        raise SeaStateError("Latitude/longitude filters were provided, but coordinates were not found in the dataset")
    mask = np.ones(latitude.shape, dtype=bool)
    if lat_min is not None:
        mask &= latitude >= lat_min
    if lat_max is not None:
        mask &= latitude <= lat_max
    if lon_min is not None and lon_max is not None and lon_min > lon_max:
        mask &= (longitude >= lon_min) | (longitude <= lon_max)
    else:
        if lon_min is not None:
            mask &= longitude >= lon_min
        if lon_max is not None:
            mask &= longitude <= lon_max
    return mask


def _validate_zone_coverage(latitude: np.ndarray | None, longitude: np.ndarray | None, config: dict[str, Any]) -> None:
    requested = {
        "latitude_min": _finite_optional(config.get("latitude_min")),
        "latitude_max": _finite_optional(config.get("latitude_max")),
        "longitude_min": _finite_optional(config.get("longitude_min")),
        "longitude_max": _finite_optional(config.get("longitude_max")),
    }
    if all(value is None for value in requested.values()):
        return
    if latitude is None or longitude is None:
        raise SeaStateError("The selected zone cannot be checked because the source has no latitude/longitude coordinates")
    finite_latitude = np.asarray(latitude, dtype=float)
    finite_latitude = finite_latitude[np.isfinite(finite_latitude)]
    finite_longitude = np.asarray(longitude, dtype=float)
    finite_longitude = finite_longitude[np.isfinite(finite_longitude)]
    if not finite_latitude.size or not finite_longitude.size:
        raise SeaStateError("The source contains no finite latitude/longitude coordinates")
    south, north = requested["latitude_min"], requested["latitude_max"]
    west, east = requested["longitude_min"], requested["longitude_max"]
    if south is not None and north is not None and south > north:
        raise SeaStateError("Zone south latitude must not be greater than north latitude")
    if south is not None and south < float(np.min(finite_latitude)) or north is not None and north > float(np.max(finite_latitude)):
        raise SeaStateError(
            f"The uploaded dataset does not cover the full selected zone latitude range. Source coverage is "
            f"{float(np.min(finite_latitude)):.3f}° to {float(np.max(finite_latitude)):.3f}°."
        )
    lon_min, lon_max = float(np.min(finite_longitude)), float(np.max(finite_longitude))
    if west is not None and east is not None and west > east:
        covers_west = lon_max >= west
        covers_east = lon_min <= east
        if not (covers_west and covers_east):
            raise SeaStateError("The uploaded dataset does not cover both sides of the selected antimeridian-crossing zone")
    elif west is not None and west < lon_min or east is not None and east > lon_max:
        raise SeaStateError(
            f"The uploaded dataset does not cover the full selected zone longitude range. Source coverage is "
            f"{lon_min:.3f}° to {lon_max:.3f}°."
        )


def _time_extent(values: Any) -> tuple[str | None, str | None]:
    if values is None:
        return None, None
    flattened = np.asarray(values).reshape(-1)
    if not flattened.size:
        return None, None
    parsed = pd.to_datetime(flattened, errors="coerce", utc=True)
    parsed = parsed[~pd.isna(parsed)]
    if not len(parsed):
        return None, None
    return parsed.min().isoformat(), parsed.max().isoformat()


def _load_csv(path: Path, config: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    frame = pd.read_csv(path)
    if frame.empty:
        raise SeaStateError("The uploaded CSV contains no observations")
    hs_name = _find_name(frame.columns, config.get("hs_variable"), HS_ALIASES, "Hs")
    tp_name = _find_name(frame.columns, config.get("tp_variable"), TP_ALIASES, "Tp")
    lat_name = _optional_name(frame.columns, LAT_ALIASES)
    lon_name = _optional_name(frame.columns, LON_ALIASES)
    time_name = _optional_name(frame.columns, TIME_ALIASES)

    hs = pd.to_numeric(frame[hs_name], errors="coerce").to_numpy(dtype=float)
    tp = pd.to_numeric(frame[tp_name], errors="coerce").to_numpy(dtype=float)
    latitude = pd.to_numeric(frame[lat_name], errors="coerce").to_numpy(dtype=float) if lat_name else None
    longitude = pd.to_numeric(frame[lon_name], errors="coerce").to_numpy(dtype=float) if lon_name else None
    mask = _coordinate_mask(latitude, longitude, config)
    if mask is not None:
        hs, tp = hs[mask], tp[mask]
    time_start, time_end = _time_extent(frame[time_name].to_numpy()[mask] if time_name and mask is not None else frame[time_name].to_numpy() if time_name else None)
    return hs, tp, {
        "hs_variable": hs_name,
        "tp_variable": tp_name,
        "latitude_variable": lat_name,
        "longitude_variable": lon_name,
        "time_variable": time_name,
        "time_start": time_start,
        "time_end": time_end,
    }


def _dataset_variable(dataset: xr.Dataset, preferred: str | None, aliases: tuple[str, ...], label: str) -> xr.DataArray:
    name = _find_name(dataset.data_vars, preferred, aliases, label)
    return dataset[name]


def _coordinate_values(array: xr.DataArray, aliases: tuple[str, ...]) -> tuple[str | None, np.ndarray | None]:
    name = _optional_name((*array.coords.keys(), *array.dims), aliases)
    if not name or name not in array.coords:
        return name, None
    values = array.coords[name].broadcast_like(array).values.reshape(-1)
    return name, np.asarray(values, dtype=float)


def _load_netcdf(path: Path, config: dict[str, Any], tp_path: Path | None) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    with xr.open_dataset(path) as hs_dataset:
        hs_array = _dataset_variable(hs_dataset, config.get("hs_variable"), HS_ALIASES, "Hs").load()
        if tp_path:
            with xr.open_dataset(tp_path) as tp_dataset:
                tp_array = _dataset_variable(tp_dataset, config.get("tp_variable"), TP_ALIASES, "Tp").load()
        else:
            tp_array = _dataset_variable(hs_dataset, config.get("tp_variable"), TP_ALIASES, "Tp").load()

    hs_array, tp_array = xr.align(hs_array, tp_array, join="inner")
    hs_array, tp_array = xr.broadcast(hs_array, tp_array)
    if hs_array.size == 0:
        raise SeaStateError("Hs and Tp have no overlapping NetCDF coordinates")
    hs = np.asarray(hs_array.values, dtype=float).reshape(-1)
    tp = np.asarray(tp_array.values, dtype=float).reshape(-1)

    lat_name, latitude = _coordinate_values(hs_array, LAT_ALIASES)
    lon_name, longitude = _coordinate_values(hs_array, LON_ALIASES)
    mask = _coordinate_mask(latitude, longitude, config)
    if mask is not None:
        hs, tp = hs[mask], tp[mask]
    time_name = _optional_name((*hs_array.coords.keys(), *hs_array.dims), TIME_ALIASES)
    time_values = None
    if time_name and time_name in hs_array.coords:
        time_values = hs_array.coords[time_name].broadcast_like(hs_array).values.reshape(-1)
        if mask is not None:
            time_values = time_values[mask]
    time_start, time_end = _time_extent(time_values)
    return hs, tp, {
        "hs_variable": hs_array.name,
        "tp_variable": tp_array.name,
        "latitude_variable": lat_name,
        "longitude_variable": lon_name,
        "time_variable": time_name,
        "time_start": time_start,
        "time_end": time_end,
    }


def load_observations(path: str | Path, config: dict[str, Any], tp_path: str | Path | None = None) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Load paired Hs/Tp observations from CSV or ERA5-style NetCDF."""
    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix == ".csv":
        if tp_path:
            raise SeaStateError("A second Tp file is supported only for NetCDF input")
        return _load_csv(source, config)
    if suffix in {".nc", ".netcdf"}:
        return _load_netcdf(source, config, Path(tp_path) if tp_path else None)
    raise SeaStateError("Historical data must be CSV, NC, or NetCDF")


def load_zone_observations(
    path: str | Path,
    config: dict[str, Any],
    tp_path: str | Path | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, dict[str, Any]]:
    """Load a bounded zone with equal contribution from valid selected records."""
    source = Path(path)
    if source.suffix.casefold() == ".csv":
        frame = pd.read_csv(source)
        if frame.empty:
            raise SeaStateError("The uploaded CSV contains no observations")
        hs_name = _find_name(frame.columns, config.get("hs_variable"), HS_ALIASES, "Hs")
        tp_name = _find_name(frame.columns, config.get("tp_variable"), TP_ALIASES, "Tp")
        lat_name = _optional_name(frame.columns, LAT_ALIASES)
        lon_name = _optional_name(frame.columns, LON_ALIASES)
        time_name = _optional_name(frame.columns, TIME_ALIASES)
        latitude = pd.to_numeric(frame[lat_name], errors="coerce").to_numpy(dtype=float) if lat_name else None
        longitude = pd.to_numeric(frame[lon_name], errors="coerce").to_numpy(dtype=float) if lon_name else None
        _validate_zone_coverage(latitude, longitude, config)
        mask = _coordinate_mask(latitude, longitude, config)
        if mask is None:
            mask = np.ones(len(frame), dtype=bool)
        hs = pd.to_numeric(frame.loc[mask, hs_name], errors="coerce").to_numpy(dtype=float)
        tp = pd.to_numeric(frame.loc[mask, tp_name], errors="coerce").to_numpy(dtype=float)
        weights = None
        time_start, time_end = _time_extent(frame.loc[mask, time_name].to_numpy() if time_name else None)
        metadata = {"hs_variable": hs_name, "tp_variable": tp_name, "latitude_variable": lat_name, "longitude_variable": lon_name, "time_variable": time_name, "time_start": time_start, "time_end": time_end}
    elif source.suffix.casefold() in {".nc", ".netcdf"}:
        with xr.open_dataset(source) as hs_dataset:
            hs_array = _dataset_variable(hs_dataset, config.get("hs_variable"), HS_ALIASES, "Hs")
            if tp_path:
                with xr.open_dataset(tp_path) as tp_dataset:
                    tp_array = _dataset_variable(tp_dataset, config.get("tp_variable"), TP_ALIASES, "Tp")
                    latitude_name, longitude_name, latitude_values, longitude_values = _array_coordinates(hs_array)
                    _validate_zone_coverage(latitude_values, longitude_values, config)
                    coordinate_config = {
                        "latitude_min": config.get("latitude_min"), "latitude_max": config.get("latitude_max"),
                        "longitude_min": config.get("longitude_min"), "longitude_max": config.get("longitude_max"),
                    }
                    lat_mask = _coordinate_mask(latitude_values, np.zeros(latitude_values.shape), {**coordinate_config, "longitude_min": None, "longitude_max": None})
                    lon_mask = _coordinate_mask(np.zeros(longitude_values.shape), longitude_values, {**coordinate_config, "latitude_min": None, "latitude_max": None})
                    lat_mask = np.ones(latitude_values.shape, dtype=bool) if lat_mask is None else lat_mask
                    lon_mask = np.ones(longitude_values.shape, dtype=bool) if lon_mask is None else lon_mask
                    hs_array = hs_array.sel({latitude_name: latitude_values[lat_mask], longitude_name: longitude_values[lon_mask]})
                    tp_latitude_name, tp_longitude_name, _, _ = _array_coordinates(tp_array)
                    tp_array = tp_array.sel({tp_latitude_name: latitude_values[lat_mask], tp_longitude_name: longitude_values[lon_mask]})
                    hs_array, tp_array = xr.align(hs_array, tp_array, join="inner")
                    hs_array, tp_array = xr.broadcast(hs_array, tp_array)
                    hs_array, tp_array = hs_array.load(), tp_array.load()
            else:
                tp_array = _dataset_variable(hs_dataset, config.get("tp_variable"), TP_ALIASES, "Tp")
                latitude_name, longitude_name, latitude_values, longitude_values = _array_coordinates(hs_array)
                _validate_zone_coverage(latitude_values, longitude_values, config)
                coordinate_config = {
                    "latitude_min": config.get("latitude_min"), "latitude_max": config.get("latitude_max"),
                    "longitude_min": config.get("longitude_min"), "longitude_max": config.get("longitude_max"),
                }
                lat_mask = _coordinate_mask(latitude_values, np.zeros(latitude_values.shape), {**coordinate_config, "longitude_min": None, "longitude_max": None})
                lon_mask = _coordinate_mask(np.zeros(longitude_values.shape), longitude_values, {**coordinate_config, "latitude_min": None, "latitude_max": None})
                lat_mask = np.ones(latitude_values.shape, dtype=bool) if lat_mask is None else lat_mask
                lon_mask = np.ones(longitude_values.shape, dtype=bool) if lon_mask is None else lon_mask
                hs_array = hs_array.sel({latitude_name: latitude_values[lat_mask], longitude_name: longitude_values[lon_mask]})
                tp_array = tp_array.sel({latitude_name: latitude_values[lat_mask], longitude_name: longitude_values[lon_mask]})
                hs_array, tp_array = xr.align(hs_array, tp_array, join="inner")
                hs_array, tp_array = xr.broadcast(hs_array, tp_array)
                hs_array, tp_array = hs_array.load(), tp_array.load()
        lat_name, latitude = _coordinate_values(hs_array, LAT_ALIASES)
        lon_name, longitude = _coordinate_values(hs_array, LON_ALIASES)
        mask = _coordinate_mask(latitude, longitude, config)
        if mask is None:
            mask = np.ones(hs_array.size, dtype=bool)
        hs = np.asarray(hs_array.values, dtype=float).reshape(-1)[mask]
        tp = np.asarray(tp_array.values, dtype=float).reshape(-1)[mask]
        weights = None
        time_name = _optional_name((*hs_array.coords.keys(), *hs_array.dims), TIME_ALIASES)
        time_values = hs_array.coords[time_name].broadcast_like(hs_array).values.reshape(-1)[mask] if time_name and time_name in hs_array.coords else None
        time_start, time_end = _time_extent(time_values)
        metadata = {"hs_variable": hs_array.name, "tp_variable": tp_array.name, "latitude_variable": lat_name, "longitude_variable": lon_name, "time_variable": time_name, "time_start": time_start, "time_end": time_end}
    else:
        raise SeaStateError("Historical data must be CSV, NC, or NetCDF")
    metadata["spatial_aggregation"] = {"mode": "zone", "weighting": "equal_observations", "selected_records": int(len(hs))}
    return hs, tp, weights, metadata


def _distance_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    """Great-circle distance used for grid-match diagnostics and route sampling."""
    radius_km = 6371.0088
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(((longitude_b - longitude_a + 180.0) % 360.0) - 180.0)
    value = math.sin(delta_lat / 2.0) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2.0) ** 2
    return radius_km * 2.0 * math.asin(min(1.0, math.sqrt(value)))


def _validated_coordinate(latitude: Any, longitude: Any, label: str) -> tuple[float, float]:
    lat = float(latitude)
    lon = float(longitude)
    if not math.isfinite(lat) or not -90.0 <= lat <= 90.0:
        raise SeaStateError(f"{label} latitude must be between -90 and 90 degrees")
    if not math.isfinite(lon) or not -180.0 <= lon <= 180.0:
        raise SeaStateError(f"{label} longitude must be between -180 and 180 degrees")
    return lat, lon


def _nearest_rectilinear_grid(
    latitude_values: np.ndarray,
    longitude_values: np.ndarray,
    latitude: float,
    longitude: float,
) -> tuple[float, float, float]:
    latitudes = np.asarray(latitude_values, dtype=float).reshape(-1)
    longitudes = np.asarray(longitude_values, dtype=float).reshape(-1)
    latitudes = latitudes[np.isfinite(latitudes)]
    longitudes = longitudes[np.isfinite(longitudes)]
    if not latitudes.size or not longitudes.size:
        raise SeaStateError("The dataset latitude/longitude coordinates are empty")
    matched_latitude = float(latitudes[np.argmin(np.abs(latitudes - latitude))])
    longitude_delta = np.abs(((longitudes - longitude + 180.0) % 360.0) - 180.0)
    matched_longitude = float(longitudes[np.argmin(longitude_delta)])
    display_longitude = ((matched_longitude + 180.0) % 360.0) - 180.0
    distance = _distance_km(latitude, longitude, matched_latitude, display_longitude)
    return matched_latitude, matched_longitude, distance


def _array_coordinates(array: xr.DataArray) -> tuple[str, str, np.ndarray, np.ndarray]:
    names = (*array.coords.keys(), *array.dims)
    latitude_name = _optional_name(names, LAT_ALIASES)
    longitude_name = _optional_name(names, LON_ALIASES)
    if not latitude_name or not longitude_name or latitude_name not in array.coords or longitude_name not in array.coords:
        raise SeaStateError("Latitude and longitude coordinates are required for a point or route selection")
    latitude_values = np.asarray(array.coords[latitude_name].values)
    longitude_values = np.asarray(array.coords[longitude_name].values)
    if latitude_values.ndim != 1 or longitude_values.ndim != 1:
        raise SeaStateError("Point and route selection currently require a rectilinear latitude/longitude grid")
    return latitude_name, longitude_name, latitude_values, longitude_values


def _selected_time_extent(array: xr.DataArray) -> tuple[str | None, str | None, str | None]:
    time_name = _optional_name((*array.coords.keys(), *array.dims), TIME_ALIASES)
    time_values = array.coords[time_name].values if time_name and time_name in array.coords else None
    time_start, time_end = _time_extent(time_values)
    return time_name, time_start, time_end


def _load_point_csv(
    path: Path,
    config: dict[str, Any],
    latitude: float,
    longitude: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    frame = pd.read_csv(path)
    if frame.empty:
        raise SeaStateError("The uploaded CSV contains no observations")
    hs_name = _find_name(frame.columns, config.get("hs_variable"), HS_ALIASES, "Hs")
    tp_name = _find_name(frame.columns, config.get("tp_variable"), TP_ALIASES, "Tp")
    lat_name = _optional_name(frame.columns, LAT_ALIASES)
    lon_name = _optional_name(frame.columns, LON_ALIASES)
    time_name = _optional_name(frame.columns, TIME_ALIASES)
    if not lat_name or not lon_name:
        raise SeaStateError("Latitude and longitude columns are required for a point selection")
    latitudes = pd.to_numeric(frame[lat_name], errors="coerce").to_numpy(dtype=float)
    longitudes = pd.to_numeric(frame[lon_name], errors="coerce").to_numpy(dtype=float)
    valid_coordinates = np.isfinite(latitudes) & np.isfinite(longitudes)
    if not np.any(valid_coordinates):
        raise SeaStateError("The uploaded CSV contains no valid grid coordinates")
    pairs = np.unique(np.column_stack((latitudes[valid_coordinates], longitudes[valid_coordinates])), axis=0)
    distances = np.array([_distance_km(latitude, longitude, point[0], point[1]) for point in pairs])
    matched_latitude, matched_longitude = map(float, pairs[int(np.argmin(distances))])
    mask = np.isclose(latitudes, matched_latitude) & np.isclose(longitudes, matched_longitude)
    hs = pd.to_numeric(frame.loc[mask, hs_name], errors="coerce").to_numpy(dtype=float)
    tp = pd.to_numeric(frame.loc[mask, tp_name], errors="coerce").to_numpy(dtype=float)
    time_start, time_end = _time_extent(frame.loc[mask, time_name].to_numpy() if time_name else None)
    return hs, tp, {
        "hs_variable": hs_name,
        "tp_variable": tp_name,
        "latitude_variable": lat_name,
        "longitude_variable": lon_name,
        "time_variable": time_name,
        "time_start": time_start,
        "time_end": time_end,
        "spatial_selection": {
            "mode": "nearest_grid_point",
            "requested": {"latitude": latitude, "longitude": longitude},
            "matched": {"latitude": matched_latitude, "longitude": matched_longitude},
            "distance_km": float(np.min(distances)),
        },
    }


def load_point_observations(
    path: str | Path,
    config: dict[str, Any],
    *,
    latitude: Any,
    longitude: Any,
    tp_path: str | Path | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Load the time series at the grid cell nearest a requested position."""
    requested_latitude, requested_longitude = _validated_coordinate(latitude, longitude, "Requested")
    source = Path(path)
    if source.suffix.casefold() == ".csv":
        if tp_path:
            raise SeaStateError("A second Tp file is supported only for NetCDF input")
        return _load_point_csv(source, config, requested_latitude, requested_longitude)
    if source.suffix.casefold() not in {".nc", ".netcdf"}:
        raise SeaStateError("Historical data must be CSV, NC, or NetCDF")

    with xr.open_dataset(source) as hs_dataset:
        hs_array = _dataset_variable(hs_dataset, config.get("hs_variable"), HS_ALIASES, "Hs")
        if tp_path:
            with xr.open_dataset(tp_path) as tp_dataset:
                tp_array = _dataset_variable(tp_dataset, config.get("tp_variable"), TP_ALIASES, "Tp")
                hs, tp, metadata = _select_netcdf_point(
                    hs_array, tp_array, requested_latitude, requested_longitude
                )
        else:
            tp_array = _dataset_variable(hs_dataset, config.get("tp_variable"), TP_ALIASES, "Tp")
            hs, tp, metadata = _select_netcdf_point(
                hs_array, tp_array, requested_latitude, requested_longitude
            )
    return hs, tp, metadata


def _select_netcdf_point(
    hs_array: xr.DataArray,
    tp_array: xr.DataArray,
    requested_latitude: float,
    requested_longitude: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    latitude_name, longitude_name, latitudes, longitudes = _array_coordinates(hs_array)
    matched_latitude, matched_longitude, distance = _nearest_rectilinear_grid(
        latitudes, longitudes, requested_latitude, requested_longitude
    )
    hs_point = hs_array.sel({latitude_name: matched_latitude, longitude_name: matched_longitude}).load()
    tp_latitude_name, tp_longitude_name, _, _ = _array_coordinates(tp_array)
    tp_point = tp_array.sel({tp_latitude_name: matched_latitude, tp_longitude_name: matched_longitude}, method="nearest").load()
    hs_point, tp_point = xr.align(hs_point, tp_point, join="inner")
    hs_point, tp_point = xr.broadcast(hs_point, tp_point)
    time_name, time_start, time_end = _selected_time_extent(hs_point)
    display_longitude = ((matched_longitude + 180.0) % 360.0) - 180.0
    return np.asarray(hs_point.values, dtype=float).reshape(-1), np.asarray(tp_point.values, dtype=float).reshape(-1), {
        "hs_variable": hs_array.name,
        "tp_variable": tp_array.name,
        "latitude_variable": latitude_name,
        "longitude_variable": longitude_name,
        "time_variable": time_name,
        "time_start": time_start,
        "time_end": time_end,
        "spatial_selection": {
            "mode": "nearest_grid_point",
            "requested": {"latitude": requested_latitude, "longitude": requested_longitude},
            "matched": {"latitude": matched_latitude, "longitude": display_longitude},
            "distance_km": distance,
        },
    }


def sample_route(coordinates: Iterable[Iterable[Any]], spacing_nm: Any = 60.0) -> tuple[list[list[float]], float]:
    """Densify a sea-route polyline at approximately uniform along-track spacing."""
    spacing = float(spacing_nm)
    if not math.isfinite(spacing) or not 5.0 <= spacing <= 500.0:
        raise SeaStateError("Route sample spacing must be between 5 and 500 nautical miles")
    points: list[tuple[float, float]] = []
    for index, coordinate in enumerate(coordinates):
        values = list(coordinate)
        if len(values) < 2:
            raise SeaStateError("Each route coordinate must contain longitude and latitude")
        latitude, longitude = _validated_coordinate(values[1], values[0], f"Route point {index + 1}")
        points.append((longitude, latitude))
    if len(points) < 2:
        raise SeaStateError("A route requires at least two coordinates")

    spacing_km = spacing * 1.852
    samples: list[list[float]] = [[points[0][0], points[0][1]]]
    length_km = 0.0
    for (longitude_a, latitude_a), (longitude_b, latitude_b) in zip(points, points[1:]):
        segment_length = _distance_km(latitude_a, longitude_a, latitude_b, longitude_b)
        length_km += segment_length
        divisions = max(1, int(math.ceil(segment_length / spacing_km)))
        longitude_delta = ((longitude_b - longitude_a + 180.0) % 360.0) - 180.0
        for division in range(1, divisions + 1):
            ratio = division / divisions
            longitude = ((longitude_a + longitude_delta * ratio + 180.0) % 360.0) - 180.0
            latitude = latitude_a + (latitude_b - latitude_a) * ratio
            samples.append([longitude, latitude])
            if len(samples) > 2500:
                raise SeaStateError("The selected route spacing creates more than 2,500 sample points")
    return samples, length_km / 1.852


def generate_sea_route(
    origin: Iterable[Any],
    destination: Iterable[Any],
    waypoints: Iterable[Iterable[Any]] | None = None,
) -> dict[str, Any]:
    """Generate a visualization-grade maritime route with the searoute package."""
    origin_values, destination_values = list(origin), list(destination)
    if len(origin_values) < 2 or len(destination_values) < 2:
        raise SeaStateError("Origin and destination must contain longitude and latitude")
    origin_latitude, origin_longitude = _validated_coordinate(origin_values[1], origin_values[0], "Origin")
    destination_latitude, destination_longitude = _validated_coordinate(destination_values[1], destination_values[0], "Destination")
    try:
        import searoute as sr
    except ImportError as exc:  # pragma: no cover - deployment boundary
        raise SeaStateError("The searoute package is not installed on this server") from exc
    route_points = [[origin_longitude, origin_latitude]]
    for index, waypoint in enumerate(waypoints or []):
        values = list(waypoint)
        if len(values) < 2:
            raise SeaStateError(f"Stopover {index + 1} must contain longitude and latitude")
        latitude, longitude = _validated_coordinate(values[1], values[0], f"Stopover {index + 1}")
        route_points.append([longitude, latitude])
    route_points.append([destination_longitude, destination_latitude])
    try:
        coordinates: list[list[float]] = []
        total_length_nm = 0.0
        for index, (start, end) in enumerate(zip(route_points, route_points[1:])):
            feature = sr.searoute(start, end, units="naut", append_orig_dest=True)
            leg = [[float(point[0]), float(point[1])] for point in feature["geometry"]["coordinates"]]
            if index and leg:
                leg = leg[1:]
            coordinates.extend(leg)
            total_length_nm += float((feature.get("properties") or {}).get("length", 0.0))
        properties = {"length": total_length_nm}
    except Exception as exc:
        raise SeaStateError(f"Unable to generate the sea route: {exc}") from exc
    if len(coordinates) < 2:
        raise SeaStateError("The sea-route network did not return a usable route")
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "properties": {
            "length_nm": float(properties.get("length", 0.0)),
            "units": "nautical miles",
            "waypoints": route_points[1:-1],
            "warning": "Visualization-grade route; not for vessel navigation.",
        },
    }


def _route_weight_factor(sample_count: int, weighting: str) -> float:
    if weighting == "route_distance":
        return float(sample_count)
    if weighting == "equal_grid_cells":
        return 1.0
    raise SeaStateError("Route weighting must be 'route_distance' or 'equal_grid_cells'")


def _route_metadata(
    coordinates: list[list[float]],
    samples: list[list[float]],
    length_nm: float,
    spacing_nm: float,
    weighting: str,
    matched_counts: Counter[tuple[float, float]],
    max_grid_distance_km: float,
    maximum_match_distance_km: float,
) -> dict[str, Any]:
    factors = {point: _route_weight_factor(count, weighting) for point, count in matched_counts.items()}
    factor_total = sum(factors.values())
    grid_points = [
        {
            "latitude": point[0],
            "longitude": ((point[1] + 180.0) % 360.0) - 180.0,
            "route_samples": matched_counts[point],
            "weight_factor": factors[point],
            "weight_percent": factors[point] * 100.0 / factor_total,
        }
        for point in matched_counts
    ]
    return {
        "mode": "route_grid_cells",
        "coordinates": coordinates,
        "sampled_coordinates": samples,
        "length_nm": length_nm,
        "sample_spacing_nm": spacing_nm,
        "sample_count": len(samples),
        "unique_grid_cells": len(grid_points),
        "weighting": weighting,
        "max_grid_distance_km": max_grid_distance_km,
        "maximum_match_distance_km": maximum_match_distance_km,
        "grid_points": grid_points,
        "warning": "Visualization-grade route; not for vessel navigation.",
    }


def _load_route_csv(
    path: Path,
    config: dict[str, Any],
    coordinates: list[list[float]],
    samples: list[list[float]],
    length_nm: float,
    spacing_nm: float,
    weighting: str,
    max_grid_distance_km: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    frame = pd.read_csv(path)
    if frame.empty:
        raise SeaStateError("The uploaded CSV contains no observations")
    hs_name = _find_name(frame.columns, config.get("hs_variable"), HS_ALIASES, "Hs")
    tp_name = _find_name(frame.columns, config.get("tp_variable"), TP_ALIASES, "Tp")
    lat_name = _optional_name(frame.columns, LAT_ALIASES)
    lon_name = _optional_name(frame.columns, LON_ALIASES)
    time_name = _optional_name(frame.columns, TIME_ALIASES)
    if not lat_name or not lon_name:
        raise SeaStateError("Latitude and longitude columns are required for route analysis")
    latitudes = pd.to_numeric(frame[lat_name], errors="coerce").to_numpy(dtype=float)
    longitudes = pd.to_numeric(frame[lon_name], errors="coerce").to_numpy(dtype=float)
    valid_coordinates = np.isfinite(latitudes) & np.isfinite(longitudes)
    pairs = np.unique(np.column_stack((latitudes[valid_coordinates], longitudes[valid_coordinates])), axis=0)
    if not pairs.size:
        raise SeaStateError("The uploaded CSV contains no valid grid coordinates")

    matched_counts: Counter[tuple[float, float]] = Counter()
    maximum_match_distance = 0.0
    for longitude, latitude in samples:
        distances = np.array([_distance_km(latitude, longitude, point[0], point[1]) for point in pairs])
        minimum_distance = float(np.min(distances))
        maximum_match_distance = max(maximum_match_distance, minimum_distance)
        if minimum_distance > max_grid_distance_km:
            raise SeaStateError(
                f"The uploaded grid does not cover the full route: a route sample is {minimum_distance:.1f} km from its nearest grid cell "
                f"(allowed {max_grid_distance_km:.1f} km)"
            )
        matched_counts[tuple(map(float, pairs[int(np.argmin(distances))]))] += 1

    hs_parts: list[np.ndarray] = []
    tp_parts: list[np.ndarray] = []
    weight_parts: list[np.ndarray] = []
    selected_mask = np.zeros(len(frame), dtype=bool)
    for (matched_latitude, matched_longitude), sample_count in matched_counts.items():
        mask = np.isclose(latitudes, matched_latitude) & np.isclose(longitudes, matched_longitude)
        hs_part = pd.to_numeric(frame.loc[mask, hs_name], errors="coerce").to_numpy(dtype=float)
        tp_part = pd.to_numeric(frame.loc[mask, tp_name], errors="coerce").to_numpy(dtype=float)
        hs_parts.append(hs_part)
        tp_parts.append(tp_part)
        weight_parts.append(np.full(hs_part.shape, _route_weight_factor(sample_count, weighting)))
        selected_mask |= mask
    time_start, time_end = _time_extent(frame.loc[selected_mask, time_name].to_numpy() if time_name else None)
    return np.concatenate(hs_parts), np.concatenate(tp_parts), np.concatenate(weight_parts), {
        "hs_variable": hs_name,
        "tp_variable": tp_name,
        "latitude_variable": lat_name,
        "longitude_variable": lon_name,
        "time_variable": time_name,
        "time_start": time_start,
        "time_end": time_end,
        "route": _route_metadata(
            coordinates, samples, length_nm, spacing_nm, weighting, matched_counts,
            max_grid_distance_km, maximum_match_distance,
        ),
    }


def load_route_observations(
    path: str | Path,
    config: dict[str, Any],
    *,
    route_coordinates: Iterable[Iterable[Any]],
    spacing_nm: Any = 60.0,
    weighting: str = "route_distance",
    max_grid_distance_km: Any = 100.0,
    tp_path: str | Path | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Match a sea route to ERA5 grid cells and return weighted paired observations."""
    coordinates = [[float(value) for value in list(point)[:2]] for point in route_coordinates]
    samples, length_nm = sample_route(coordinates, spacing_nm)
    spacing = float(spacing_nm)
    maximum_allowed_distance = float(max_grid_distance_km)
    if not math.isfinite(maximum_allowed_distance) or not 1.0 <= maximum_allowed_distance <= 1000.0:
        raise SeaStateError("Maximum route-to-grid distance must be between 1 and 1,000 kilometres")
    source = Path(path)
    if source.suffix.casefold() == ".csv":
        if tp_path:
            raise SeaStateError("A second Tp file is supported only for NetCDF input")
        return _load_route_csv(
            source, config, coordinates, samples, length_nm, spacing, weighting, maximum_allowed_distance
        )
    if source.suffix.casefold() not in {".nc", ".netcdf"}:
        raise SeaStateError("Historical data must be CSV, NC, or NetCDF")

    with xr.open_dataset(source) as hs_dataset:
        hs_array = _dataset_variable(hs_dataset, config.get("hs_variable"), HS_ALIASES, "Hs")
        if tp_path:
            tp_dataset_context = xr.open_dataset(tp_path)
            tp_dataset = tp_dataset_context.__enter__()
        else:
            tp_dataset_context = None
            tp_dataset = hs_dataset
        try:
            tp_array = _dataset_variable(tp_dataset, config.get("tp_variable"), TP_ALIASES, "Tp")
            latitude_name, longitude_name, latitudes, longitudes = _array_coordinates(hs_array)
            matched_counts: Counter[tuple[float, float]] = Counter()
            maximum_match_distance = 0.0
            for longitude, latitude in samples:
                matched_latitude, matched_longitude, match_distance = _nearest_rectilinear_grid(
                    latitudes, longitudes, latitude, longitude
                )
                maximum_match_distance = max(maximum_match_distance, match_distance)
                if match_distance > maximum_allowed_distance:
                    raise SeaStateError(
                        f"The uploaded grid does not cover the full route: a route sample is {match_distance:.1f} km from its nearest grid cell "
                        f"(allowed {maximum_allowed_distance:.1f} km)"
                    )
                matched_counts[(matched_latitude, matched_longitude)] += 1

            tp_latitude_name, tp_longitude_name, _, _ = _array_coordinates(tp_array)
            hs_parts: list[np.ndarray] = []
            tp_parts: list[np.ndarray] = []
            weight_parts: list[np.ndarray] = []
            for (matched_latitude, matched_longitude), sample_count in matched_counts.items():
                hs_cell = hs_array.sel({latitude_name: matched_latitude, longitude_name: matched_longitude}).load()
                tp_cell = tp_array.sel(
                    {tp_latitude_name: matched_latitude, tp_longitude_name: matched_longitude}, method="nearest"
                ).load()
                hs_cell, tp_cell = xr.align(hs_cell, tp_cell, join="inner")
                hs_cell, tp_cell = xr.broadcast(hs_cell, tp_cell)
                hs_values = np.asarray(hs_cell.values, dtype=float).reshape(-1)
                hs_parts.append(hs_values)
                tp_parts.append(np.asarray(tp_cell.values, dtype=float).reshape(-1))
                weight_parts.append(np.full(hs_values.shape, _route_weight_factor(sample_count, weighting)))
            time_name, time_start, time_end = _selected_time_extent(hs_array)
        finally:
            if tp_dataset_context is not None:
                tp_dataset_context.__exit__(None, None, None)
    return np.concatenate(hs_parts), np.concatenate(tp_parts), np.concatenate(weight_parts), {
        "hs_variable": hs_array.name,
        "tp_variable": tp_array.name,
        "latitude_variable": latitude_name,
        "longitude_variable": longitude_name,
        "time_variable": time_name,
        "time_start": time_start,
        "time_end": time_end,
        "route": _route_metadata(
            coordinates, samples, length_nm, spacing, weighting, matched_counts,
            maximum_allowed_distance, maximum_match_distance,
        ),
    }


def _edges(start: float, maximum: float, width: float) -> np.ndarray:
    upper = max(start + width, math.ceil((maximum + 1e-12) / width) * width)
    edge_count = int(round((upper - start) / width)) + 1
    if edge_count > 121:
        raise SeaStateError("The selected bin width creates more than 120 bins on one axis")
    return start + np.arange(edge_count, dtype=float) * width


def build_scatter(
    hs: np.ndarray,
    tp: np.ndarray,
    *,
    weights: np.ndarray | None = None,
    hs_bin_width: float = 0.5,
    tp_bin_width: float = 1.0,
    source_name: str = "historical data",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Clean paired observations and construct count/probability matrices."""
    hs_width = float(hs_bin_width)
    tp_width = float(tp_bin_width)
    if not math.isfinite(hs_width) or hs_width <= 0:
        raise SeaStateError("Hs bin width must be positive")
    if not math.isfinite(tp_width) or tp_width <= 0:
        raise SeaStateError("Tp bin width must be positive")
    hs_values = np.asarray(hs, dtype=float).reshape(-1)
    tp_values = np.asarray(tp, dtype=float).reshape(-1)
    if hs_values.shape != tp_values.shape:
        raise SeaStateError("Hs and Tp must contain the same number of paired observations")
    weight_values = None if weights is None else np.asarray(weights, dtype=float).reshape(-1)
    if weight_values is not None and weight_values.shape != hs_values.shape:
        raise SeaStateError("Weights must contain one value for every paired Hs/Tp observation")
    finite_pair = np.isfinite(hs_values) & np.isfinite(tp_values)
    physically_valid = (hs_values >= 0.0) & (tp_values > 0.0)
    valid = finite_pair & physically_valid
    missing_value_observations = int(np.count_nonzero(~finite_pair))
    out_of_range_observations = int(np.count_nonzero(finite_pair & ~physically_valid))
    invalid_weight_observations = 0
    if weight_values is not None:
        valid_weight = np.isfinite(weight_values) & (weight_values > 0.0)
        invalid_weight_observations = int(np.count_nonzero(finite_pair & physically_valid & ~valid_weight))
        valid &= valid_weight
    missing = int(valid.size - np.count_nonzero(valid))
    hs_valid = hs_values[valid]
    tp_valid = tp_values[valid]
    weights_valid = weight_values[valid] if weight_values is not None else None
    if hs_valid.size < 2:
        if (metadata or {}).get("spatial_aggregation", {}).get("mode") == "zone":
            raise SeaStateError("The selected zone contains no usable ocean wave data. Choose bounds containing ERA5 ocean grid cells.")
        raise SeaStateError("The selection contains fewer than two usable paired Hs/Tp observations")

    hs_edges = _edges(0.0, float(np.max(hs_valid)), hs_width)
    tp_start = max(0.0, math.floor(float(np.min(tp_valid)) / tp_width) * tp_width)
    tp_edges = _edges(tp_start, float(np.max(tp_valid)), tp_width)
    counts, _, _ = np.histogram2d(hs_valid, tp_valid, bins=(hs_edges, tp_edges), weights=weights_valid)
    if weights_valid is None:
        counts = counts.astype(int)
        probability_denominator = float(hs_valid.size)
    else:
        probability_denominator = float(np.sum(weights_valid))
    probabilities = counts.astype(float) * (100.0 / probability_denominator)

    states: list[dict[str, Any]] = []
    for hs_index, tp_index in np.argwhere(counts > 0):
        states.append({
            "hs_index": int(hs_index),
            "tp_index": int(tp_index),
            "hs_low": float(hs_edges[hs_index]),
            "hs_high": float(hs_edges[hs_index + 1]),
            "tp_low": float(tp_edges[tp_index]),
            "tp_high": float(tp_edges[tp_index + 1]),
            "hs": float((hs_edges[hs_index] + hs_edges[hs_index + 1]) / 2.0),
            "tp": float((tp_edges[tp_index] + tp_edges[tp_index + 1]) / 2.0),
            "count": float(counts[hs_index, tp_index]) if weights_valid is not None else int(counts[hs_index, tp_index]),
            "probability": float(probabilities[hs_index, tp_index]),
        })
    states.sort(key=lambda item: (-item["probability"], item["hs_index"], item["tp_index"]))
    details = dict(metadata or {})
    return {
        "source_name": source_name,
        "valid_observations": int(hs_valid.size),
        "missing_observations": missing,
        "missing_value_observations": missing_value_observations,
        "out_of_range_observations": out_of_range_observations,
        "invalid_weight_observations": invalid_weight_observations,
        "weighted": weights_valid is not None,
        "effective_weight": probability_denominator,
        "hs_bin_width": hs_width,
        "tp_bin_width": tp_width,
        "hs_edges": hs_edges.tolist(),
        "tp_edges": tp_edges.tolist(),
        "counts": counts.tolist(),
        "probabilities": probabilities.tolist(),
        "top_states": states[:12],
        "selected_state": states[0],
        "probability_sum": float(np.sum(probabilities)),
        **details,
    }


def demo_scatter(hs_bin_width: float = 0.5, tp_bin_width: float = 1.0) -> dict[str, Any]:
    """Return deterministic, correlated historical observations for UI evaluation."""
    rng = np.random.default_rng(1616)
    count = 67_248
    regimes = rng.choice(3, size=count, p=(0.70, 0.23, 0.07))
    hs = np.empty(count)
    hs[regimes == 0] = rng.gamma(3.0, 0.62, size=np.count_nonzero(regimes == 0))
    hs[regimes == 1] = rng.gamma(5.0, 0.62, size=np.count_nonzero(regimes == 1))
    hs[regimes == 2] = rng.gamma(7.0, 0.72, size=np.count_nonzero(regimes == 2))
    hs = np.clip(hs, 0.05, 8.4)
    tp = 4.4 + 1.85 * hs + rng.normal(0.0, 1.35, size=count)
    tp += np.where(regimes == 2, 1.2, 0.0)
    tp = np.clip(tp, 3.0, 21.0)
    hs = np.concatenate((hs, np.full(124, np.nan)))
    tp = np.concatenate((tp, np.full(124, np.nan)))
    return build_scatter(
        hs,
        tp,
        hs_bin_width=hs_bin_width,
        tp_bin_width=tp_bin_width,
        source_name="ERA5 demonstration · Zone 16",
        metadata={
            "time_start": "2016-01-01T00:00:00+00:00",
            "time_end": "2025-12-31T23:00:00+00:00",
            "time_resolution": "Hourly",
            "zone": "Zone 16",
            "hs_variable": "significant_height_of_combined_wind_waves_and_swell",
            "tp_variable": "peak_wave_period",
        },
    )
