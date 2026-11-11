"""Create a small, closed OBJ barge for installation and workflow checks."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
os.environ.setdefault("CAPYTAINE_CACHE_DIR", str(ROOT / ".cache"))

import capytaine as cpt
import meshio


def main() -> None:
    output = ROOT / "meshes" / "demo_barge.obj"
    output.parent.mkdir(parents=True, exist_ok=True)
    barge = cpt.mesh_parallelepiped(
        size=(4.0, 2.0, 2.0),
        center=(0.0, 0.0, 0.0),
        resolution=(6, 4, 4),
        name="demo_barge",
    )
    meshio.write(output, meshio.Mesh(points=barge.vertices, cells=[("quad", barge.faces)]))
    print(f"Created {output} with {barge.nb_faces} quadrilateral panels.")


if __name__ == "__main__":
    main()
