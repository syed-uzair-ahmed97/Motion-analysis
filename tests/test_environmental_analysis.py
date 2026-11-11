from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from analysis.sea_state import (
    SeaStateError,
    build_scatter,
    demo_scatter,
    load_observations,
    load_point_observations,
    load_route_observations,
    load_zone_observations,
    inspect_wave_source_pair,
    inspect_wave_source_collection,
    resolve_wave_source_paths,
)
from analysis.spectral_response import calculate_response, jonswap_spectrum


class SeaStateTests(unittest.TestCase):
    def test_probability_matrix_is_normalized(self) -> None:
        result = build_scatter(
            np.array([0.2, 0.7, 1.2, 1.4, np.nan]),
            np.array([4.2, 5.1, 6.3, 6.8, 7.0]),
            hs_bin_width=0.5,
            tp_bin_width=1.0,
        )
        self.assertEqual(result["valid_observations"], 4)
        self.assertEqual(result["missing_observations"], 1)
        self.assertAlmostEqual(result["probability_sum"], 100.0, places=10)
        self.assertEqual(sum(sum(row) for row in result["counts"]), 4)

    def test_demo_is_deterministic_and_complete(self) -> None:
        first = demo_scatter()
        second = demo_scatter()
        self.assertEqual(first["counts"], second["counts"])
        self.assertEqual(first["valid_observations"], 67_248)
        self.assertEqual(first["missing_observations"], 124)

    def test_quality_control_reports_missing_and_physical_rejections_separately(self) -> None:
        result = build_scatter(
            np.array([1.0, 1.5, np.nan, -0.2, 2.0]),
            np.array([6.0, 7.0, 7.0, 8.0, 0.0]),
        )
        self.assertEqual(result["valid_observations"], 2)
        self.assertEqual(result["missing_value_observations"], 1)
        self.assertEqual(result["out_of_range_observations"], 2)
        self.assertEqual(result["missing_observations"], 3)

    def test_separate_era5_hs_and_tp_netcdf_files_are_paired(self) -> None:
        coordinates = {
            "valid_time": pd.date_range("2026-01-01", periods=2, freq="h"),
            "latitude": [50.0, 49.5],
            "longitude": [1.0, 1.5],
        }
        shape = (2, 2, 2)
        with tempfile.TemporaryDirectory() as directory:
            hs_path = Path(directory) / "significant_wave_height.nc"
            tp_path = Path(directory) / "peak_wave_period.nc"
            xr.Dataset({"swh": (("valid_time", "latitude", "longitude"), np.full(shape, 2.4))}, coords=coordinates).to_netcdf(hs_path)
            xr.Dataset({"pp1d": (("valid_time", "latitude", "longitude"), np.full(shape, 9.5))}, coords=coordinates).to_netcdf(tp_path)
            hs, tp, metadata = load_observations(hs_path, {}, tp_path)
        self.assertEqual(hs.size, 8)
        self.assertTrue(np.allclose(hs, 2.4))
        self.assertTrue(np.allclose(tp, 9.5))
        self.assertEqual(metadata["time_variable"], "valid_time")

    def test_weighted_scatter_normalizes_weighted_counts(self) -> None:
        result = build_scatter(
            np.array([0.2, 1.2]),
            np.array([4.2, 6.2]),
            weights=np.array([1.0, 3.0]),
            hs_bin_width=1.0,
            tp_bin_width=1.0,
        )
        populated = sorted(state["probability"] for state in result["top_states"])
        self.assertEqual(populated, [25.0, 75.0])
        self.assertTrue(result["weighted"])
        self.assertEqual(result["effective_weight"], 4.0)

    def test_zone_selection_uses_equal_observation_contributions(self) -> None:
        frame = pd.DataFrame({
            "latitude": [0.0, 60.0], "longitude": [1.0, 1.0],
            "hs": [1.0, 3.0], "tp": [6.0, 10.0],
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zone.csv"
            frame.to_csv(path, index=False)
            hs, tp, weights, metadata = load_zone_observations(
                path, {"latitude_min": 0, "latitude_max": 60, "longitude_min": 1, "longitude_max": 1}
            )
        self.assertTrue(np.allclose(hs, [1.0, 3.0]))
        self.assertTrue(np.allclose(tp, [6.0, 10.0]))
        self.assertIsNone(weights)
        self.assertEqual(metadata["spatial_aggregation"]["weighting"], "equal_observations")

    def test_zone_rejects_partial_geographic_coverage(self) -> None:
        frame = pd.DataFrame({"latitude": [50.0, 51.0], "longitude": [1.0, 2.0], "hs": [1.0, 2.0], "tp": [6.0, 7.0]})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "regional.csv"
            frame.to_csv(path, index=False)
            with self.assertRaisesRegex(SeaStateError, "does not cover the full selected zone"):
                load_zone_observations(path, {"latitude_min": 49.0, "latitude_max": 52.0, "longitude_min": 0.0, "longitude_max": 3.0})

    def test_two_netcdf_files_are_identified_by_contents_not_names(self) -> None:
        coordinates = {"valid_time": pd.date_range("2016-01-01", periods=2, freq="6h"), "latitude": [50.0], "longitude": [1.0]}
        with tempfile.TemporaryDirectory() as directory:
            misleading_hs = Path(directory) / "second-file.nc"
            misleading_tp = Path(directory) / "first-file.nc"
            xr.Dataset({"swh": (("valid_time", "latitude", "longitude"), np.ones((2, 1, 1)))}, coords=coordinates).to_netcdf(misleading_hs)
            xr.Dataset({"pp1d": (("valid_time", "latitude", "longitude"), np.full((2, 1, 1), 8.0))}, coords=coordinates).to_netcdf(misleading_tp)
            hs_path, tp_path, manifest = resolve_wave_source_paths([misleading_tp, misleading_hs])
        self.assertEqual(hs_path.name, "second-file.nc")
        self.assertEqual(tp_path.name, "first-file.nc")
        self.assertEqual(manifest["years"], [2016])
        self.assertEqual(manifest["pairing"], "separate_hs_tp")

    def test_multi_year_collection_pairs_each_period(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for year in (2016, 2017):
                coordinates = {"valid_time": pd.date_range(f"{year}-01-01", periods=2, freq="6h"), "latitude": [50.0], "longitude": [1.0]}
                hs_path = Path(directory) / f"wave-a-{year}.nc"
                tp_path = Path(directory) / f"wave-b-{year}.nc"
                xr.Dataset({"swh": (("valid_time", "latitude", "longitude"), np.ones((2, 1, 1)))}, coords=coordinates).to_netcdf(hs_path)
                xr.Dataset({"pp1d": (("valid_time", "latitude", "longitude"), np.full((2, 1, 1), 8.0))}, coords=coordinates).to_netcdf(tp_path)
                paths.extend([tp_path, hs_path])
            manifest = inspect_wave_source_collection(paths)
        self.assertEqual(manifest["file_count"], 4)
        self.assertEqual(manifest["period_count"], 2)
        self.assertEqual(manifest["years"], [2016, 2017])
        self.assertTrue(all(group["pairing"] == "separate_hs_tp" for group in manifest["groups"]))

    def test_multi_year_collection_reports_hs_tp_mismatch(self) -> None:
        coordinates = {"valid_time": pd.date_range("2016-01-01", periods=2, freq="6h"), "latitude": [50.0], "longitude": [1.0]}
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for name in ("hs-one.nc", "hs-two.nc"):
                path = Path(directory) / name
                xr.Dataset({"swh": (("valid_time", "latitude", "longitude"), np.ones((2, 1, 1)))}, coords=coordinates).to_netcdf(path)
                paths.append(path)
            tp_path = Path(directory) / "tp.nc"
            xr.Dataset({"pp1d": (("valid_time", "latitude", "longitude"), np.full((2, 1, 1), 8.0))}, coords=coordinates).to_netcdf(tp_path)
            paths.append(tp_path)
            with self.assertRaisesRegex(SeaStateError, r"found 2 Hs file\(s\) and 1 Tp file\(s\)"):
                inspect_wave_source_collection(paths)

    def test_point_selection_uses_nearest_era5_grid_cell(self) -> None:
        coordinates = {
            "valid_time": pd.date_range("2026-01-01", periods=2, freq="h"),
            "latitude": [50.0, 49.5],
            "longitude": [1.0, 1.5],
        }
        hs_values = np.arange(8, dtype=float).reshape(2, 2, 2) + 1.0
        tp_values = hs_values + 5.0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "era5.nc"
            xr.Dataset({
                "swh": (("valid_time", "latitude", "longitude"), hs_values),
                "pp1d": (("valid_time", "latitude", "longitude"), tp_values),
            }, coords=coordinates).to_netcdf(path)
            hs, tp, metadata = load_point_observations(path, {}, latitude=49.6, longitude=1.4)
        self.assertTrue(np.allclose(hs, [4.0, 8.0]))
        self.assertTrue(np.allclose(tp, [9.0, 13.0]))
        self.assertEqual(metadata["spatial_selection"]["matched"], {"latitude": 49.5, "longitude": 1.5})
        self.assertGreater(metadata["spatial_selection"]["distance_km"], 0.0)

    def test_route_selection_returns_unique_grid_cells_and_weights(self) -> None:
        coordinates = {
            "valid_time": pd.date_range("2026-01-01", periods=2, freq="h"),
            "latitude": [50.0, 49.5],
            "longitude": [1.0, 1.5],
        }
        shape = (2, 2, 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "era5.nc"
            xr.Dataset({
                "swh": (("valid_time", "latitude", "longitude"), np.full(shape, 2.4)),
                "pp1d": (("valid_time", "latitude", "longitude"), np.full(shape, 9.5)),
            }, coords=coordinates).to_netcdf(path)
            hs, tp, weights, metadata = load_route_observations(
                path,
                {},
                route_coordinates=[[1.0, 50.0], [1.5, 49.5]],
                spacing_nm=500.0,
                weighting="equal_grid_cells",
            )
        self.assertEqual(hs.size, 4)
        self.assertEqual(tp.size, 4)
        self.assertTrue(np.allclose(weights, 1.0))
        self.assertEqual(metadata["route"]["unique_grid_cells"], 2)

    def test_route_selection_rejects_dataset_without_route_coverage(self) -> None:
        frame = pd.DataFrame({
            "time": ["2026-01-01T00:00:00", "2026-01-01T01:00:00"],
            "latitude": [50.0, 50.0],
            "longitude": [1.0, 1.0],
            "hs": [1.2, 1.4],
            "tp": [6.5, 6.8],
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "regional.csv"
            frame.to_csv(path, index=False)
            with self.assertRaisesRegex(SeaStateError, "does not cover the full route"):
                load_route_observations(
                    path,
                    {},
                    route_coordinates=[[1.0, 50.0], [-74.0, 40.7]],
                    spacing_nm=500.0,
                    max_grid_distance_km=100.0,
                )


class SpectralResponseTests(unittest.TestCase):
    def test_jonswap_recovers_requested_wave_height(self) -> None:
        result = jonswap_spectrum(2.5, 10.0, 3.3, points=2000)
        self.assertTrue(all(value >= 0 for value in result["jonswap"]))
        self.assertAlmostEqual(result["hm0"], 2.5, delta=0.12)

    def test_point_coordinate_changes_rotational_acceleration(self) -> None:
        omega = np.linspace(0.2, 2.5, 30)
        rows = []
        for dof in ("Heave", "Roll", "Pitch"):
            amplitude = {"Heave": 0.8, "Roll": 0.02, "Pitch": 0.015}[dof]
            for value in omega:
                rows.append({
                    "omega": value,
                    "wave_direction": math.pi / 2,
                    "radiating_dof": dof,
                    "real": amplitude,
                    "imag": amplitude * 0.2,
                    "g": 9.81,
                })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rao.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            origin = calculate_response(
                path,
                hs=2.5,
                tp=10.0,
                gamma=3.3,
                heading_deg=90.0,
                speed_knots=0.0,
                point={"x": 0.0, "y": 0.0, "z": 0.0},
                duration_days=10.0,
                exceedance_probability=0.01,
            )
            remote = calculate_response(
                path,
                hs=2.5,
                tp=10.0,
                gamma=3.3,
                heading_deg=90.0,
                speed_knots=0.0,
                point={"x": 50.0, "y": 8.0, "z": 5.0},
                duration_days=10.0,
                exceedance_probability=0.01,
            )
        self.assertNotAlmostEqual(remote["point_results"]["Az"]["rms"], origin["point_results"]["Az"]["rms"])
        self.assertAlmostEqual(remote["inputs"]["heading_selected_deg"], 90.0)


if __name__ == "__main__":
    unittest.main()
