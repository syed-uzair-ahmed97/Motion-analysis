"""Local API and static server for the Motion Analysis dashboard."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


DASHBOARD_DIR = Path(__file__).resolve().parent
PROJECT_DIR = DASHBOARD_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from analysis.sea_state import (
    SeaStateError,
    build_scatter,
    demo_scatter,
    generate_sea_route,
    load_observations,
    load_zone_observations,
    load_point_observations,
    load_route_observations,
    inspect_wave_source_collection,
    resolve_wave_source_collection,
)
from analysis.spectral_response import ResponseError, calculate_response, jonswap_spectrum

DIST_DIR = DASHBOARD_DIR / "dist"
JOBS_DIR = DASHBOARD_DIR / "jobs"
SEA_STATE_JOBS_DIR = DASHBOARD_DIR / "sea_state_jobs"
RESPONSE_JOBS_DIR = DASHBOARD_DIR / "response_jobs"
RUNNER = PROJECT_DIR / "run_hydrodynamics.py"
EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="capytaine-analysis")
STATE_LOCK = threading.Lock()
JOB_STATE: dict[str, dict[str, Any]] = {}

JOBS_DIR.mkdir(parents=True, exist_ok=True)
SEA_STATE_JOBS_DIR.mkdir(parents=True, exist_ok=True)
RESPONSE_JOBS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Motion Analysis Dashboard", version="1.0.0")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_directory(job_id: str) -> Path:
    try:
        uuid.UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Unknown analysis job") from exc
    directory = (JOBS_DIR / job_id).resolve()
    if directory.parent != JOBS_DIR.resolve():
        raise HTTPException(status_code=404, detail="Unknown analysis job")
    return directory


def stored_job_directory(root: Path, job_id: str, label: str) -> Path:
    try:
        uuid.UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown {label} job") from exc
    directory = (root / job_id).resolve()
    if directory.parent != root.resolve():
        raise HTTPException(status_code=404, detail=f"Unknown {label} job")
    return directory


def state_path(job_id: str) -> Path:
    return job_directory(job_id) / "status.json"


def write_state(job_id: str, **updates: Any) -> dict[str, Any]:
    with STATE_LOCK:
        state = JOB_STATE.setdefault(
            job_id,
            {"job_id": job_id, "status": "queued", "created_at": utc_now(), "outputs": []},
        )
        state.update(updates)
        state["updated_at"] = utc_now()
        state_path(job_id).write_text(json.dumps(state, indent=2), encoding="utf-8")
        return dict(state)


def read_state(job_id: str) -> dict[str, Any]:
    with STATE_LOCK:
        if job_id in JOB_STATE:
            return dict(JOB_STATE[job_id])
    path = state_path(job_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Unknown analysis job")
    state = json.loads(path.read_text(encoding="utf-8"))
    with STATE_LOCK:
        JOB_STATE[job_id] = state
    return state


def finite_number(value: Any, name: str, *, minimum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not (float("-inf") < number < float("inf")):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return number


def build_inertia_matrix(body: dict[str, Any]) -> list[list[float]] | None:
    if body.get("inertia_mode") != "custom":
        return None
    mass = finite_number(body.get("mass_kg"), "Mass", minimum=0.0)
    inertia = body.get("inertia", {})
    ixx = finite_number(inertia.get("ixx"), "Ixx", minimum=0.0)
    iyy = finite_number(inertia.get("iyy"), "Iyy", minimum=0.0)
    izz = finite_number(inertia.get("izz"), "Izz", minimum=0.0)
    ixy = finite_number(inertia.get("ixy", 0.0), "Ixy")
    ixz = finite_number(inertia.get("ixz", 0.0), "Ixz")
    iyz = finite_number(inertia.get("iyz", 0.0), "Iyz")
    return [
        [mass, 0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, mass, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, mass, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, ixx, ixy, ixz],
        [0.0, 0.0, 0.0, ixy, iyy, iyz],
        [0.0, 0.0, 0.0, ixz, iyz, izz],
    ]


def build_solver_config(payload: dict[str, Any], mesh_name: str) -> dict[str, Any]:
    mesh = payload.get("mesh", {})
    body = payload.get("body", {})
    environment = payload.get("environment", {})
    analysis = payload.get("analysis", {})
    response = payload.get("response", {})

    center_of_mass = [
        finite_number(value, f"Centre of gravity {axis}")
        for value, axis in zip(body.get("center_of_mass_m", []), ("x", "y", "z"), strict=False)
    ]
    if len(center_of_mass) != 3:
        raise ValueError("Centre of gravity must have x, y and z values")

    mass_value = body.get("mass_kg")
    mass = None if mass_value in (None, "") else finite_number(mass_value, "Mass", minimum=0.0)
    dofs = analysis.get("degrees_of_freedom", [])
    allowed_dofs = {"Surge", "Sway", "Heave", "Roll", "Pitch", "Yaw"}
    if not dofs or not set(dofs).issubset(allowed_dofs):
        raise ValueError("Select at least one valid degree of freedom")

    headings = [finite_number(value, "Wave heading") for value in analysis.get("wave_headings_deg", [])]
    if not headings:
        raise ValueError("Provide at least one wave heading")

    depth_value = environment.get("water_depth_m")
    water_depth = None if depth_value in (None, "") else finite_number(depth_value, "Water depth", minimum=0.0)
    roll_damping_target = finite_number(
        response.get("roll_damping_target_percent", 0.0),
        "Roll damping target",
        minimum=0.0,
    )
    if roll_damping_target > 0.0 and "Roll" not in dofs:
        raise ValueError("Enable the Roll degree of freedom before setting a roll damping target")
    stiffness = {
        dof: finite_number(response.get("mooring_stiffness_diagonal", {}).get(dof, 0.0), f"{dof} mooring stiffness", minimum=0.0)
        for dof in dofs
    }
    period_min = finite_number(analysis.get("period_min_s"), "Minimum wave period", minimum=1e-6)
    period_max = finite_number(analysis.get("period_max_s"), "Maximum wave period", minimum=1e-6)
    if period_max <= period_min:
        raise ValueError("Maximum wave period must be greater than the minimum wave period")

    return {
        "project": {"name": str(body.get("name") or Path(mesh_name).stem)},
        "mesh": {
            "path": mesh_name,
            "scale_to_m": finite_number(mesh.get("scale_to_m", 1.0), "Mesh scale", minimum=1e-12),
            "translation_m": [0.0, 0.0, 0.0],
            "heal": bool(mesh.get("heal", True)),
            "closed_mesh": bool(mesh.get("closed_mesh", True)),
            "flip_normals": bool(mesh.get("flip_normals", False)),
            "lid": {"enabled": bool(mesh.get("lid_enabled", False)), "faces_max_radius_m": None},
        },
        "body": {
            "center_of_mass_m": center_of_mass,
            "mass_kg": mass,
            "inertia_matrix_6x6": build_inertia_matrix(body),
            "hydrostatic_stiffness_6x6": None,
        },
        "environment": {
            "water_density_kg_m3": finite_number(environment.get("water_density_kg_m3", 1025.0), "Water density", minimum=0.0),
            "gravity_m_s2": finite_number(environment.get("gravity_m_s2", 9.81), "Gravity", minimum=0.0),
            "free_surface_z_m": finite_number(environment.get("free_surface_z_m", 0.0), "Waterline z"),
            "water_depth_m": water_depth,
        },
        "analysis": {
            "wave_period_s": {
                "min": period_min,
                "max": period_max,
                "count": int(finite_number(analysis.get("period_count"), "Wave period count", minimum=1.0)),
            },
            "wave_headings_deg": headings,
            "degrees_of_freedom": dofs,
        },
        "response": {
            "roll_damping_target_percent": roll_damping_target,
            "mooring_stiffness_diagonal": stiffness,
        },
        "solver": {"n_jobs": 1, "progress_bar": True, "log_level": "INFO"},
        "output": {"directory": "results"},
    }


def run_analysis_job(job_id: str) -> None:
    directory = job_directory(job_id)
    log_path = directory / "solver.log"
    write_state(job_id, status="running", message="Solving hydrodynamic cases")
    environment = os.environ.copy()
    environment.setdefault("CAPYTAINE_CACHE_DIR", str(PROJECT_DIR / ".cache"))
    environment.setdefault("MPLCONFIGDIR", str(PROJECT_DIR / ".matplotlib"))
    command = [sys.executable, str(RUNNER), str(directory / "config.yaml")]
    try:
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.run(
                command,
                cwd=PROJECT_DIR,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if process.returncode != 0:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-5000:]
            write_state(job_id, status="failed", message="Capytaine analysis failed", error=tail)
            return
        results_dir = directory / "results"
        outputs = [
            {"name": path.name, "size": path.stat().st_size}
            for path in sorted(results_dir.iterdir())
            if path.is_file()
        ]
        write_state(job_id, status="completed", message="Analysis complete", outputs=outputs)
    except Exception as exc:  # pragma: no cover - last-resort job boundary
        write_state(job_id, status="failed", message="Analysis failed", error=str(exc))


@app.get("/api/health")
def health() -> dict[str, Any]:
    import capytaine as cpt

    return {
        "status": "ok",
        "capytaine": cpt.__version__,
        "runner": RUNNER.is_file(),
        "modules": ["sea-states", "hydrodynamics", "spectral-response"],
    }


@app.get("/api/analysis")
def list_analyses() -> dict[str, Any]:
    jobs: list[dict[str, Any]] = []
    for directory in JOBS_DIR.iterdir():
        if not directory.is_dir():
            continue
        path = directory / "status.json"
        if not path.is_file():
            continue
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        state["rao_available"] = (directory / "results" / "rao.csv").is_file()
        jobs.append(state)
    jobs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {"jobs": jobs[:100]}


@app.get("/api/sea-states/demo")
def get_demo_sea_states(hs_bin_width: float = 0.5, tp_bin_width: float = 1.0) -> dict[str, Any]:
    try:
        result = demo_scatter(hs_bin_width, tp_bin_width)
    except SeaStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job_id": "demo", "created_at": utc_now(), **result}


async def read_upload(upload: UploadFile, *, limit: int = 250 * 1024 * 1024) -> tuple[str, bytes]:
    filename = Path(upload.filename or "historical-data").name
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail=f"{filename} is empty")
    if len(content) > limit:
        raise HTTPException(status_code=413, detail=f"{filename} exceeds the 250 MB dashboard limit")
    return filename, content


def write_scatter_csv(path: Path, result: dict[str, Any]) -> None:
    hs_edges = result["hs_edges"]
    tp_edges = result["tp_edges"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["hs_low_m", "hs_high_m", "tp_low_s", "tp_high_s", "count", "probability_percent"])
        for hs_index, row in enumerate(result["counts"]):
            for tp_index, count in enumerate(row):
                writer.writerow([
                    hs_edges[hs_index],
                    hs_edges[hs_index + 1],
                    tp_edges[tp_index],
                    tp_edges[tp_index + 1],
                    count,
                    result["probabilities"][hs_index][tp_index],
                ])


def parse_sea_state_payload(payload: str) -> dict[str, Any]:
    try:
        config = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Sea-state configuration is not valid JSON") from exc
    if not isinstance(config, dict):
        raise HTTPException(status_code=400, detail="Sea-state configuration must be a JSON object")
    return config


async def store_sea_state_uploads(
    uploads: list[UploadFile],
    job_kind: str,
) -> tuple[str, list[tuple[Path, Path | None]], dict[Path, str], dict[str, Any]]:
    if not uploads:
        raise HTTPException(status_code=400, detail="Select at least one Hs/Tp source file")
    if len(uploads) > 100:
        raise HTTPException(status_code=400, detail="Select no more than 100 files per analysis")
    job_id = str(uuid.uuid4())
    directory = stored_job_directory(SEA_STATE_JOBS_DIR, job_id, job_kind)
    directory.mkdir(parents=True, exist_ok=False)
    paths = []
    name_by_path: dict[Path, str] = {}
    for index, upload in enumerate(uploads):
        name, content = await read_upload(upload)
        if Path(name).suffix.casefold() not in {".csv", ".nc", ".netcdf"}:
            raise HTTPException(status_code=400, detail=f"{name} must be CSV, NC, or NetCDF")
        path = directory / f"{index:03d}_{name}"
        path.write_bytes(content)
        paths.append(path)
        name_by_path[path] = name
    try:
        segments, manifest = resolve_wave_source_collection(paths)
    except SeaStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    manifest["files"] = [
        {**item, "file_name": name_by_path[paths[item["input_index"]]]}
        for item in manifest["files"]
    ]
    return job_id, segments, name_by_path, manifest


def collect_sea_state_uploads(
    data_files: list[UploadFile] | None,
    data_file: UploadFile | None,
    tp_file: UploadFile | None,
) -> list[UploadFile]:
    uploads = [upload for upload in (data_files or []) if upload.filename]
    uploads.extend(upload for upload in (data_file, tp_file) if upload is not None and upload.filename)
    return uploads


def combined_source_name(manifest: dict[str, Any], prefix: str = "") -> str:
    names = [item["file_name"] for item in manifest["files"]]
    label = " + ".join(names) if len(names) <= 3 else f"{len(names)} files · {manifest['years'][0]}–{manifest['years'][-1]}"
    return prefix + label


def merge_segment_metadata(metadata_items: list[dict[str, Any]]) -> dict[str, Any]:
    merged = dict(metadata_items[0])
    starts = [item.get("time_start") for item in metadata_items if item.get("time_start")]
    ends = [item.get("time_end") for item in metadata_items if item.get("time_end")]
    merged["time_start"] = min(starts) if starts else None
    merged["time_end"] = max(ends) if ends else None
    if "spatial_aggregation" in merged:
        merged["spatial_aggregation"] = {
            **merged["spatial_aggregation"],
            "selected_records": sum(item.get("spatial_aggregation", {}).get("selected_records", 0) for item in metadata_items),
        }
    return merged


@app.post("/api/sea-states/inspect")
async def inspect_sea_state_uploads(
    data_files: list[UploadFile] | None = File(None),
    data_file: UploadFile | None = File(None),
    tp_file: UploadFile | None = File(None),
) -> dict[str, Any]:
    selected_uploads = collect_sea_state_uploads(data_files, data_file, tp_file)
    if not selected_uploads:
        raise HTTPException(status_code=400, detail="Select at least one Hs/Tp source file")
    if len(selected_uploads) > 100:
        raise HTTPException(status_code=400, detail="Select no more than 100 files per analysis")
    with tempfile.TemporaryDirectory(prefix="motion-source-inspection-") as directory:
        paths = []
        upload_details = []
        for index, upload in enumerate(selected_uploads):
            name, content = await read_upload(upload)
            path = Path(directory) / f"{index}-{name}"
            path.write_bytes(content)
            paths.append(path)
            upload_details.append((name, len(content)))
        try:
            manifest = inspect_wave_source_collection(paths)
        except (SeaStateError, OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    for item in manifest["files"]:
        name, size = upload_details[item["input_index"]]
        item["file_name"] = name
        item["size_bytes"] = size
    return manifest


def persist_scatter(directory: Path, job_id: str, result: dict[str, Any]) -> dict[str, Any]:
    persisted = {"job_id": job_id, "created_at": utc_now(), **result}
    (directory / "scatter.json").write_text(json.dumps(persisted, indent=2), encoding="utf-8")
    write_scatter_csv(directory / "scatter.csv", persisted)
    return persisted


def sea_state_method(result: dict[str, Any]) -> str:
    if result.get("route"):
        return "route"
    if result.get("spatial_selection"):
        return "location"
    return "zone"


@app.get("/api/sea-states")
def list_sea_state_results() -> list[dict[str, Any]]:
    items = []
    for path in SEA_STATE_JOBS_DIR.glob("*/scatter.json"):
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items.append({
            "job_id": result.get("job_id", path.parent.name),
            "created_at": result.get("created_at"),
            "title": result.get("title") or result.get("source_name") or "Sea-state analysis",
            "method": sea_state_method(result),
            "source_name": result.get("source_name"),
            "time_start": result.get("time_start"),
            "time_end": result.get("time_end"),
            "valid_observations": result.get("valid_observations", 0),
            "selected_state": result.get("selected_state"),
        })
    return sorted(items, key=lambda item: item.get("created_at") or "", reverse=True)


@app.get("/api/sea-states/{job_id}/files/{filename}")
def download_sea_state_file(job_id: str, filename: str) -> FileResponse:
    if filename not in {"scatter.json", "scatter.csv"}:
        raise HTTPException(status_code=404, detail="Sea-state export not found")
    path = stored_job_directory(SEA_STATE_JOBS_DIR, job_id, "sea-state") / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Sea-state export not found")
    return FileResponse(path, filename=filename, media_type="application/json" if filename.endswith("json") else "text/csv")


@app.post("/api/sea-states")
async def create_sea_states(
    data_files: list[UploadFile] | None = File(None),
    data_file: UploadFile | None = File(None),
    payload: str = Form("{}"),
    tp_file: UploadFile | None = File(None),
) -> dict[str, Any]:
    config = parse_sea_state_payload(payload)
    job_id, segments, _, manifest = await store_sea_state_uploads(collect_sea_state_uploads(data_files, data_file, tp_file), "sea-state")
    directory = segments[0][0].parent
    try:
        loaded = [load_zone_observations(hs_path, config, tp_path) for hs_path, tp_path in segments]
        hs = np.concatenate([item[0] for item in loaded])
        tp = np.concatenate([item[1] for item in loaded])
        weights = np.concatenate([item[2] for item in loaded]) if loaded[0][2] is not None else None
        metadata = merge_segment_metadata([item[3] for item in loaded])
        result = build_scatter(
            hs,
            tp,
            weights=weights,
            hs_bin_width=config.get("hs_bin_width", 0.5),
            tp_bin_width=config.get("tp_bin_width", 1.0),
            source_name=combined_source_name(manifest),
            metadata={**metadata, "source_manifest": manifest, "filters": {key: config.get(key) for key in (
                "latitude_min", "latitude_max", "longitude_min", "longitude_max"
            )}},
        )
    except (SeaStateError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return persist_scatter(directory, job_id, result)


@app.post("/api/sea-routes")
def create_sea_route(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return generate_sea_route(
            payload.get("origin", []),
            payload.get("destination", []),
            payload.get("waypoints", []),
        )
    except (SeaStateError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sea-states/location")
async def create_location_sea_states(
    data_files: list[UploadFile] | None = File(None),
    data_file: UploadFile | None = File(None),
    payload: str = Form("{}"),
    tp_file: UploadFile | None = File(None),
) -> dict[str, Any]:
    config = parse_sea_state_payload(payload)
    job_id, segments, _, manifest = await store_sea_state_uploads(collect_sea_state_uploads(data_files, data_file, tp_file), "location-sea-state")
    try:
        loaded = [load_point_observations(hs_path, config, latitude=config.get("latitude"), longitude=config.get("longitude"), tp_path=tp_path) for hs_path, tp_path in segments]
        hs = np.concatenate([item[0] for item in loaded])
        tp = np.concatenate([item[1] for item in loaded])
        metadata = merge_segment_metadata([item[2] for item in loaded])
        result = build_scatter(
            hs,
            tp,
            hs_bin_width=config.get("hs_bin_width", 0.5),
            tp_bin_width=config.get("tp_bin_width", 1.0),
            source_name=combined_source_name(manifest),
            metadata={**metadata, "source_manifest": manifest},
        )
    except (SeaStateError, OSError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return persist_scatter(segments[0][0].parent, job_id, result)


@app.post("/api/sea-states/route")
async def create_route_sea_states(
    data_files: list[UploadFile] | None = File(None),
    data_file: UploadFile | None = File(None),
    payload: str = Form("{}"),
    tp_file: UploadFile | None = File(None),
) -> dict[str, Any]:
    config = parse_sea_state_payload(payload)
    job_id, segments, _, manifest = await store_sea_state_uploads(collect_sea_state_uploads(data_files, data_file, tp_file), "route-sea-state")
    try:
        loaded = [load_route_observations(hs_path, config, route_coordinates=config.get("route_coordinates", []), spacing_nm=config.get("sample_spacing_nm", 60.0), weighting=config.get("weighting", "route_distance"), max_grid_distance_km=config.get("max_grid_distance_km", 100.0), tp_path=tp_path) for hs_path, tp_path in segments]
        hs = np.concatenate([item[0] for item in loaded])
        tp = np.concatenate([item[1] for item in loaded])
        weights = np.concatenate([item[2] for item in loaded])
        metadata = merge_segment_metadata([item[3] for item in loaded])
        result = build_scatter(
            hs,
            tp,
            weights=weights,
            hs_bin_width=config.get("hs_bin_width", 0.5),
            tp_bin_width=config.get("tp_bin_width", 1.0),
            source_name=combined_source_name(manifest, "Route · "),
            metadata={**metadata, "source_manifest": manifest},
        )
    except (SeaStateError, OSError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return persist_scatter(segments[0][0].parent, job_id, result)


@app.get("/api/sea-states/{job_id}")
def get_sea_states(job_id: str) -> dict[str, Any]:
    path = stored_job_directory(SEA_STATE_JOBS_DIR, job_id, "sea-state") / "scatter.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Sea-state result not found")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/spectrum")
def preview_spectrum(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return jonswap_spectrum(
            payload.get("hs"),
            payload.get("tp"),
            payload.get("gamma", 3.3),
            points=int(payload.get("points", 600)),
        )
    except (ResponseError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def write_response_files(directory: Path, result: dict[str, Any]) -> Path:
    summary_path = directory / "response_summary.json"
    summary_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    omega = result["omega"]
    encounter = result["encounter_omega"]
    with (directory / "spectrum.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["omega_rad_s", "encounter_omega_rad_s", "pm_m2_s_per_rad", "jonswap_m2_s_per_rad", "ax_psd", "ay_psd", "az_psd"])
        for index in range(len(omega)):
            writer.writerow([
                omega[index],
                encounter[index],
                result["pm"][index],
                result["jonswap"][index],
                result["point_acceleration_spectra"]["Ax"][index],
                result["point_acceleration_spectra"]["Ay"][index],
                result["point_acceleration_spectra"]["Az"][index],
            ])
    with (directory / "dof_response.csv").open("w", newline="", encoding="utf-8") as stream:
        columns = ["dof", "available", "motion_rms", "acceleration_rms", "peak_period_s", "motion_unit", "acceleration_unit"]
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(result["dof_results"])
    package = directory / "response_package.zip"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in ("response_summary.json", "spectrum.csv", "dof_response.csv"):
            archive.write(directory / filename, arcname=filename)
    return package


@app.post("/api/responses")
def create_response(payload: dict[str, Any]) -> dict[str, Any]:
    rao_job_id = str(payload.get("rao_job_id", ""))
    rao_path = job_directory(rao_job_id) / "results" / "rao.csv"
    if not rao_path.is_file():
        raise HTTPException(status_code=400, detail="Select a completed hydrodynamic analysis containing rao.csv")
    try:
        result = calculate_response(
            rao_path,
            hs=payload.get("hs"),
            tp=payload.get("tp"),
            gamma=payload.get("gamma", 3.3),
            heading_deg=payload.get("heading_deg", 0.0),
            speed_knots=payload.get("speed_knots", 0.0),
            point=payload.get("point", {}),
            duration_days=payload.get("duration_days", 42.0),
            exceedance_probability=payload.get("exceedance_probability", 0.01),
        )
    except (ResponseError, TypeError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response_id = str(uuid.uuid4())
    directory = stored_job_directory(RESPONSE_JOBS_DIR, response_id, "response")
    directory.mkdir(parents=True, exist_ok=False)
    result = {
        "response_id": response_id,
        "created_at": utc_now(),
        "rao_job_id": rao_job_id,
        **result,
    }
    package = write_response_files(directory, result)
    result["download_url"] = f"/api/responses/{response_id}/download"
    result["package_size"] = package.stat().st_size
    return result


@app.get("/api/responses/{response_id}/download")
def download_response(response_id: str) -> FileResponse:
    path = stored_job_directory(RESPONSE_JOBS_DIR, response_id, "response") / "response_package.zip"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Response package not found")
    return FileResponse(path, filename="motion-response-package.zip", media_type="application/zip")


@app.post("/api/analysis")
async def create_analysis(mesh_file: UploadFile = File(...), payload: str = Form(...)) -> dict[str, Any]:
    filename = Path(mesh_file.filename or "hull.obj").name
    if Path(filename).suffix.lower() != ".obj":
        raise HTTPException(status_code=400, detail="Please upload an OBJ mesh")
    try:
        parsed_payload = json.loads(payload)
        config = build_solver_config(parsed_payload, filename)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_id = str(uuid.uuid4())
    directory = job_directory(job_id)
    directory.mkdir(parents=True, exist_ok=False)
    mesh_bytes = await mesh_file.read()
    if not mesh_bytes:
        raise HTTPException(status_code=400, detail="The OBJ file is empty")
    if len(mesh_bytes) > 250 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="The OBJ file exceeds the 250 MB dashboard limit")
    (directory / filename).write_bytes(mesh_bytes)
    (directory / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    write_state(job_id, status="queued", message="Queued for analysis", filename=filename)
    EXECUTOR.submit(run_analysis_job, job_id)
    return read_state(job_id)


@app.get("/api/analysis/{job_id}")
def get_analysis(job_id: str) -> dict[str, Any]:
    state = read_state(job_id)
    log_path = job_directory(job_id) / "solver.log"
    if log_path.is_file():
        state["log_tail"] = log_path.read_text(encoding="utf-8", errors="replace")[-8000:]
    return state


@app.get("/api/analysis/{job_id}/files/{filename}")
def get_result_file(job_id: str, filename: str) -> FileResponse:
    results_dir = (job_directory(job_id) / "results").resolve()
    path = (results_dir / Path(filename).name).resolve()
    if path.parent != results_dir or not path.is_file():
        raise HTTPException(status_code=404, detail="Result file not found")
    return FileResponse(path, filename=path.name)


@app.post("/api/analysis/{job_id}/open-folder")
def open_result_folder(job_id: str) -> dict[str, str]:
    results_dir = job_directory(job_id) / "results"
    if not results_dir.is_dir():
        raise HTTPException(status_code=404, detail="Results folder not found")
    if os.name != "nt":
        raise HTTPException(status_code=501, detail="Open folder is available on Windows only")
    os.startfile(results_dir)  # type: ignore[attr-defined]
    return {"status": "opened"}


if DIST_DIR.is_dir():
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="dashboard")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Motion Analysis dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
