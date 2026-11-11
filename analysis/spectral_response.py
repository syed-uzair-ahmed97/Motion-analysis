"""JONSWAP, complex RAO response, and point-acceleration calculations."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DOFS = ("Surge", "Sway", "Heave", "Roll", "Pitch", "Yaw")
ROTATIONAL_DOFS = {"Roll", "Pitch", "Yaw"}


class ResponseError(ValueError):
    """Raised when a spectral response request is invalid."""


def _integral(values: np.ndarray, coordinate: np.ndarray) -> float:
    return float(np.trapezoid(values, coordinate))


def _validate_range(value: Any, name: str, minimum: float, maximum: float, *, inclusive_minimum: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ResponseError(f"{name} must be a number") from exc
    minimum_ok = number >= minimum if inclusive_minimum else number > minimum
    if not math.isfinite(number) or not minimum_ok or number > maximum:
        operator = ">=" if inclusive_minimum else ">"
        raise ResponseError(f"{name} must be {operator} {minimum} and <= {maximum}")
    return number


def jonswap_spectrum(
    hs: float,
    tp: float,
    gamma: float = 3.3,
    *,
    points: int = 600,
    omega: np.ndarray | None = None,
) -> dict[str, Any]:
    """Generate the PM/JONSWAP spectrum used by the supplied MATLAB reference."""
    hs_value = _validate_range(hs, "Hs", 0.0, 30.0)
    tp_value = _validate_range(tp, "Tp", 0.0, 60.0)
    gamma_value = _validate_range(gamma, "JONSWAP gamma", 1.0, 10.0, inclusive_minimum=True)
    point_count = int(points)
    if point_count < 100 or point_count > 4000:
        raise ResponseError("Spectrum points must be between 100 and 4000")
    omega_peak = 2.0 * math.pi / tp_value
    w = np.asarray(omega, dtype=float) if omega is not None else np.linspace(0.01, 7.0 * omega_peak, point_count)
    if w.ndim != 1 or w.size < 2 or np.any(~np.isfinite(w)) or np.any(w <= 0) or np.any(np.diff(w) <= 0):
        raise ResponseError("Angular-frequency coordinates must be finite, positive, and increasing")
    with np.errstate(over="ignore", under="ignore", divide="ignore", invalid="ignore"):
        pm = (
            (5.0 / 16.0)
            * hs_value**2
            * omega_peak**4
            * w**-5
            * np.exp(-(5.0 / 4.0) * (w / omega_peak) ** -4)
        )
    pm = np.nan_to_num(pm, nan=0.0, posinf=0.0, neginf=0.0)
    sigma = np.where(w <= omega_peak, 0.07, 0.09)
    peak_shape = np.exp(-0.5 * ((w - omega_peak) / (sigma * omega_peak)) ** 2)
    normalization = 0.2 / (0.065 * gamma_value**0.803 + 0.135)
    jonswap = normalization * pm * gamma_value**peak_shape
    m0 = _integral(jonswap, w)
    hm0 = 4.0 * math.sqrt(max(m0, 0.0))
    return {
        "hs": hs_value,
        "tp": tp_value,
        "gamma": gamma_value,
        "omega_peak": omega_peak,
        "m0": m0,
        "hm0": hm0,
        "omega": w.tolist(),
        "pm": pm.tolist(),
        "jonswap": jonswap.tolist(),
    }


def _circular_distance(values: np.ndarray, target: float) -> np.ndarray:
    return np.abs((values - target + 180.0) % 360.0 - 180.0)


def load_rao_frame(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"omega", "wave_direction", "radiating_dof", "real", "imag"}
    missing = required.difference(frame.columns)
    if missing:
        raise ResponseError(f"RAO CSV is missing columns: {', '.join(sorted(missing))}")
    frame = frame.copy()
    for column in ("omega", "wave_direction", "real", "imag"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["radiating_dof"] = frame["radiating_dof"].astype(str).str.strip().str.title()
    frame = frame.dropna(subset=["omega", "wave_direction", "real", "imag"])
    frame = frame[frame["radiating_dof"].isin(DOFS)]
    if frame.empty:
        raise ResponseError("RAO CSV contains no usable complex RAO rows")
    frame["heading_deg"] = np.rad2deg(frame["wave_direction"].to_numpy(dtype=float)) % 360.0
    return frame


def _complex_rao(frame: pd.DataFrame, dof: str, heading: float, omega: np.ndarray) -> np.ndarray:
    rows = frame[(frame["radiating_dof"] == dof) & np.isclose(frame["heading_deg"], heading, atol=1e-7)]
    if rows.empty:
        return np.zeros_like(omega, dtype=complex)
    grouped = rows.groupby("omega", as_index=False)[["real", "imag"]].mean().sort_values("omega")
    source_omega = grouped["omega"].to_numpy(dtype=float)
    real = np.interp(omega, source_omega, grouped["real"].to_numpy(dtype=float), left=0.0, right=0.0)
    imag = np.interp(omega, source_omega, grouped["imag"].to_numpy(dtype=float), left=0.0, right=0.0)
    return real + 1j * imag


def _spectral_metrics(spectrum: np.ndarray, omega: np.ndarray, encounter: np.ndarray, duration_seconds: float, alpha: float) -> dict[str, float | None]:
    m0 = max(_integral(spectrum, omega), 0.0)
    m2 = max(_integral(encounter**2 * spectrum, omega), 0.0)
    rms = math.sqrt(m0)
    tz = 2.0 * math.pi * math.sqrt(m0 / m2) if m0 > 0 and m2 > 0 else None
    if tz and duration_seconds > tz:
        cycles = max(duration_seconds / tz, 1.0)
        factor = math.sqrt(max(0.0, 2.0 * math.log(cycles / alpha)))
    else:
        factor = 0.0
    return {
        "m0": m0,
        "m2": m2,
        "rms": rms,
        "zero_crossing_period_s": tz,
        "expected_max": rms * factor,
        "extreme_factor": factor,
    }


def calculate_response(
    rao_csv_path: str | Path,
    *,
    hs: float,
    tp: float,
    gamma: float,
    heading_deg: float,
    speed_knots: float,
    point: dict[str, Any],
    duration_days: float,
    exceedance_probability: float,
    points: int = 700,
) -> dict[str, Any]:
    """Combine a JONSWAP sea state with complex RAOs and evaluate point acceleration."""
    heading_requested = float(heading_deg) % 360.0
    if not math.isfinite(heading_requested):
        raise ResponseError("Heading must be finite")
    speed = _validate_range(speed_knots, "Speed", 0.0, 80.0, inclusive_minimum=True)
    duration = _validate_range(duration_days, "Duration", 0.0, 3650.0)
    alpha = _validate_range(exceedance_probability, "Exceedance probability", 0.0, 1.0)
    coordinates = {
        axis: _validate_range(abs(float(point.get(axis, 0.0))), f"Point {axis} magnitude", 0.0, 100_000.0, inclusive_minimum=True)
        * (-1.0 if float(point.get(axis, 0.0)) < 0 else 1.0)
        for axis in ("x", "y", "z")
    }

    frame = load_rao_frame(rao_csv_path)
    headings = np.sort(frame["heading_deg"].unique().astype(float))
    selected_heading = float(headings[int(np.argmin(_circular_distance(headings, heading_requested)))])
    spectrum = jonswap_spectrum(hs, tp, gamma, points=points)
    omega = np.asarray(spectrum["omega"], dtype=float)
    wave_spectrum = np.asarray(spectrum["jonswap"], dtype=float)
    gravity = float(frame["g"].dropna().iloc[0]) if "g" in frame and not frame["g"].dropna().empty else 9.81
    speed_ms = speed * 0.514444
    encounter_signed = omega - (speed_ms / gravity) * omega**2 * math.cos(math.radians(heading_requested))
    encounter = np.abs(encounter_signed)

    rao = {dof: _complex_rao(frame, dof, selected_heading, omega) for dof in DOFS}
    available_dofs = sorted(frame[np.isclose(frame["heading_deg"], selected_heading, atol=1e-7)]["radiating_dof"].unique())
    missing_dofs = [dof for dof in DOFS if dof not in available_dofs]
    duration_seconds = duration * 24.0 * 3600.0

    dof_rows: list[dict[str, Any]] = []
    motion_spectra: dict[str, list[float]] = {}
    acceleration_spectra: dict[str, list[float]] = {}
    for dof in DOFS:
        motion_density = np.abs(rao[dof]) ** 2 * wave_spectrum
        acceleration_density = encounter**4 * motion_density
        motion_m0 = max(_integral(motion_density, omega), 0.0)
        acceleration_metrics = _spectral_metrics(acceleration_density, omega, encounter, duration_seconds, alpha)
        peak_index = int(np.argmax(motion_density)) if np.any(motion_density > 0) else 0
        peak_period = 2.0 * math.pi / encounter[peak_index] if encounter[peak_index] > 1e-10 else None
        dof_rows.append({
            "dof": dof,
            "available": dof in available_dofs,
            "motion_rms": math.sqrt(motion_m0),
            "acceleration_rms": acceleration_metrics["rms"],
            "peak_period_s": peak_period,
            "motion_unit": "rad" if dof in ROTATIONAL_DOFS else "m",
            "acceleration_unit": "rad/s²" if dof in ROTATIONAL_DOFS else "m/s²",
        })
        motion_spectra[dof] = motion_density.tolist()
        acceleration_spectra[dof] = acceleration_density.tolist()

    x, y, z = coordinates["x"], coordinates["y"], coordinates["z"]
    frequency_squared = encounter**2
    point_transfer = {
        "Ax": -frequency_squared * (rao["Surge"] + z * rao["Pitch"] - y * rao["Yaw"]) - gravity * rao["Pitch"],
        "Ay": -frequency_squared * (rao["Sway"] + x * rao["Yaw"] - z * rao["Roll"]) + gravity * rao["Roll"],
        "Az": -frequency_squared * (rao["Heave"] - x * rao["Pitch"] + y * rao["Roll"]),
    }
    point_spectra: dict[str, list[float]] = {}
    point_results: dict[str, dict[str, float | None]] = {}
    for axis, transfer in point_transfer.items():
        density = np.abs(transfer) ** 2 * wave_spectrum
        point_spectra[axis] = density.tolist()
        point_results[axis] = _spectral_metrics(density, omega, encounter, duration_seconds, alpha)

    warnings: list[str] = []
    if missing_dofs:
        warnings.append(f"Unavailable RAO DOFs were treated as zero: {', '.join(missing_dofs)}")
    if abs(selected_heading - heading_requested) > 1e-7:
        warnings.append(f"Requested heading {heading_requested:g}° used nearest solved heading {selected_heading:g}°")
    if np.any(encounter_signed < 0):
        warnings.append("Following-sea encounter frequency changes sign; absolute encounter frequency is used for time derivatives")

    return {
        "method": "Complex RAO phase · absolute-frequency integration · small-angle rigid-body point transformation",
        "inputs": {
            "hs": float(spectrum["hs"]),
            "tp": float(spectrum["tp"]),
            "gamma": float(spectrum["gamma"]),
            "heading_requested_deg": heading_requested,
            "heading_selected_deg": selected_heading,
            "speed_knots": speed,
            "point": coordinates,
            "duration_days": duration,
            "exceedance_probability": alpha,
        },
        "available_headings_deg": headings.tolist(),
        "available_dofs": available_dofs,
        "missing_dofs": missing_dofs,
        "omega": omega.tolist(),
        "encounter_omega": encounter.tolist(),
        "jonswap": wave_spectrum.tolist(),
        "pm": spectrum["pm"],
        "spectrum_metrics": {key: spectrum[key] for key in ("omega_peak", "m0", "hm0")},
        "motion_spectra": motion_spectra,
        "dof_acceleration_spectra": acceleration_spectra,
        "point_acceleration_spectra": point_spectra,
        "dof_results": dof_rows,
        "point_results": point_results,
        "warnings": warnings,
    }
