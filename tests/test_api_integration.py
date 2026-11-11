import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from fastapi.testclient import TestClient

from dashboard.backend import app


class EnvironmentalApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_reports_all_modules(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["modules"],
            ["sea-states", "hydrodynamics", "spectral-response"],
        )

    def test_demo_scatter_and_spectrum_preview(self):
        scatter_response = self.client.get(
            "/api/sea-states/demo",
            params={"hs_bin_width": 0.5, "tp_bin_width": 1.0},
        )
        self.assertEqual(scatter_response.status_code, 200)
        scatter = scatter_response.json()
        self.assertAlmostEqual(sum(map(sum, scatter["probabilities"])), 100.0, places=8)

        state = scatter["selected_state"]
        spectrum_response = self.client.post(
            "/api/spectrum",
            json={"hs": state["hs"], "tp": state["tp"], "gamma": 3.3, "points": 300},
        )
        self.assertEqual(spectrum_response.status_code, 200)
        spectrum = spectrum_response.json()
        self.assertEqual(len(spectrum["omega"]), 300)
        self.assertAlmostEqual(spectrum["hm0"], state["hs"], delta=0.025)

    def test_csv_upload_builds_scatter(self):
        content = b"time,hs,tp\n2026-01-01T00:00:00,1.2,6.5\n2026-01-01T01:00:00,2.1,8.2\n"
        response = self.client.post(
            "/api/sea-states",
            files={"data_file": ("observations.csv", content, "text/csv")},
            data={"payload": '{"hs_bin_width": 0.5, "tp_bin_width": 1.0}'},
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["valid_observations"], 2)
        history = self.client.get("/api/sea-states")
        self.assertEqual(history.status_code, 200)
        self.assertIn(result["job_id"], [item["job_id"] for item in history.json()])
        self.assertEqual(self.client.get(f"/api/sea-states/{result['job_id']}/files/scatter.csv").status_code, 200)
        self.assertEqual(self.client.get(f"/api/sea-states/{result['job_id']}/files/scatter.json").status_code, 200)

    def test_upload_inspection_reports_year_variables_and_coverage(self):
        coordinates = {"valid_time": pd.date_range("2016-01-01", periods=2, freq="6h"), "latitude": [49.5, 50.0], "longitude": [1.0, 1.5]}
        with tempfile.TemporaryDirectory() as directory:
            hs_path = Path(directory) / "not_named_hs.nc"
            tp_path = Path(directory) / "not_named_tp.nc"
            xr.Dataset({"swh": (("valid_time", "latitude", "longitude"), np.ones((2, 2, 2)))}, coords=coordinates).to_netcdf(hs_path)
            xr.Dataset({"pp1d": (("valid_time", "latitude", "longitude"), np.full((2, 2, 2), 8.0))}, coords=coordinates).to_netcdf(tp_path)
            response = self.client.post("/api/sea-states/inspect", files={"data_file": ("mystery-a.nc", hs_path.read_bytes(), "application/x-netcdf"), "tp_file": ("mystery-b.nc", tp_path.read_bytes(), "application/x-netcdf")})
        self.assertEqual(response.status_code, 200)
        manifest = response.json()
        self.assertEqual(manifest["pairing"], "separate_hs_tp")
        self.assertEqual(manifest["years"], [2016])
        self.assertEqual([item["role"] for item in manifest["files"]], ["hs", "tp"])
        self.assertEqual(manifest["coverage"]["latitude_min"], 49.5)

    def test_multi_year_combined_files_are_aggregated(self):
        files = []
        for year, hs in ((2016, 1.2), (2017, 2.2)):
            content = f"time,latitude,longitude,hs,tp\n{year}-01-01T00:00:00,50,1,{hs},7.0\n{year}-01-01T06:00:00,50,1,{hs + 0.1},7.5\n".encode()
            files.append(("data_files", (f"waves-{year}.csv", content, "text/csv")))
        inspection = self.client.post("/api/sea-states/inspect", files=files)
        self.assertEqual(inspection.status_code, 200)
        self.assertEqual(inspection.json()["years"], [2016, 2017])
        self.assertEqual(inspection.json()["period_count"], 2)
        response = self.client.post("/api/sea-states", files=files, data={"payload": json.dumps({"latitude_min": 50, "latitude_max": 50, "longitude_min": 1, "longitude_max": 1})})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["valid_observations"], 4)
        self.assertEqual(response.json()["source_manifest"]["file_count"], 2)

    def test_location_upload_reports_requested_and_nearest_grid_point(self):
        content = (
            b"time,latitude,longitude,hs,tp\n"
            b"2026-01-01T00:00:00,50.0,1.0,1.2,6.5\n"
            b"2026-01-01T01:00:00,50.0,1.0,2.1,8.2\n"
            b"2026-01-01T00:00:00,49.5,1.5,3.2,10.5\n"
            b"2026-01-01T01:00:00,49.5,1.5,3.4,10.8\n"
        )
        response = self.client.post(
            "/api/sea-states/location",
            files={"data_file": ("era5.csv", content, "text/csv")},
            data={"payload": json.dumps({"latitude": 49.6, "longitude": 1.4})},
        )
        self.assertEqual(response.status_code, 200)
        selection = response.json()["spatial_selection"]
        self.assertEqual(selection["matched"], {"latitude": 49.5, "longitude": 1.5})
        self.assertGreater(selection["distance_km"], 0.0)

    def test_route_upload_builds_weighted_scatter(self):
        content = (
            b"time,latitude,longitude,hs,tp\n"
            b"2026-01-01T00:00:00,50.0,1.0,1.2,6.5\n"
            b"2026-01-01T01:00:00,50.0,1.0,1.4,6.8\n"
            b"2026-01-01T00:00:00,49.5,1.5,3.2,10.5\n"
            b"2026-01-01T01:00:00,49.5,1.5,3.4,10.8\n"
        )
        payload = {
            "route_coordinates": [[1.0, 50.0], [1.5, 49.5]],
            "sample_spacing_nm": 500,
            "weighting": "equal_grid_cells",
        }
        response = self.client.post(
            "/api/sea-states/route",
            files={"data_file": ("era5.csv", content, "text/csv")},
            data={"payload": json.dumps(payload)},
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result["weighted"])
        self.assertEqual(result["route"]["unique_grid_cells"], 2)
        self.assertAlmostEqual(result["probability_sum"], 100.0)

    def test_sea_route_preview_returns_geojson(self):
        response = self.client.post(
            "/api/sea-routes",
            json={"origin": [2.35, 48.86], "destination": [-74.0, 40.7]},
        )
        self.assertEqual(response.status_code, 200)
        route = response.json()
        self.assertEqual(route["geometry"]["type"], "LineString")
        self.assertGreater(len(route["geometry"]["coordinates"]), 2)
        self.assertGreater(route["properties"]["length_nm"], 1000)

    def test_sea_route_preview_accepts_stopover(self):
        response = self.client.post(
            "/api/sea-routes",
            json={"origin": [4.48, 51.92], "destination": [-74.04, 40.68], "waypoints": [[-5.53, 50.11]]},
        )
        self.assertEqual(response.status_code, 200)
        route = response.json()
        self.assertEqual(route["properties"]["waypoints"], [[-5.53, 50.11]])
        self.assertGreater(len(route["geometry"]["coordinates"]), 2)


if __name__ == "__main__":
    unittest.main()
