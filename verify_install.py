"""Verify the Capytaine motion-analysis environment."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
os.environ.setdefault("CAPYTAINE_CACHE_DIR", str(ROOT / ".cache"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib"))

import capytaine as cpt
import matplotlib
import meshio
import netCDF4
import numpy
import pandas
import scipy
import xarray
import yaml


def main() -> None:
    packages = {
        "capytaine": cpt.__version__,
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "xarray": xarray.__version__,
        "pandas": pandas.__version__,
        "matplotlib": matplotlib.__version__,
        "meshio": meshio.__version__,
        "netCDF4": netCDF4.__version__,
        "PyYAML": yaml.__version__,
    }
    for name, version in packages.items():
        print(f"OK  {name}: {version}")
    print(f"OK  meshio OBJ reader: {'obj' in meshio._helpers.reader_map}")
    for optional in ("vtk", "gmsh", "pygmsh", "joblib", "jupyterlab"):
        state = "installed" if importlib.util.find_spec(optional) is not None else "not installed (optional)"
        print(f"--  {optional}: {state}")


if __name__ == "__main__":
    main()
