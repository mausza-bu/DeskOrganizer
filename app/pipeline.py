"""Pipeline: UI payload -> sized modules -> layout algorithm -> positioned CAD.

Coordinate conventions:
- Algorithm grid uses (x=row, y=col); w=column-extent, h=row-extent.
- CAD uses (x=horizontal, y=vertical). A cell is 10mm.
- Mapping: cad_x = placement.y * 10, cad_y = placement.x * 10.
"""

import math
import cadquery as cq

from app.algorithm_generate import GRID_SIZE, generate_layout
from app.cad.pen_holder_cadquery import make_pen_holder
from app.cad.sd_holder_cadquery import make_sd_holder
from app.cad.storage_tray import storage_tray

CELL_MM = 10
TRAY_HEIGHT_MM = {"short": 30, "high": 80}


def pen_rows(num_pens: int) -> int:
    if num_pens <= 1:
        return 1
    if num_pens <= 4:
        return 2
    return 3


def _bbox_cells(workplane: cq.Workplane) -> tuple[int, int]:
    bb = workplane.val().BoundingBox()
    return math.ceil(bb.xlen / CELL_MM), math.ceil(bb.ylen / CELL_MM)


def _to_positive_octant(cad: cq.Workplane) -> cq.Workplane:
    """Shift a shape so its bounding box starts at (0, 0, 0)."""
    bb = cad.val().BoundingBox()
    return cad.translate((-bb.xmin, -bb.ymin, -bb.zmin))


def build_space(available_space: list[list[int]], grid_size: int = GRID_SIZE) -> list[list[int]]:
    grid = [[0] * grid_size for _ in range(grid_size)]
    for cell in available_space:
        r, c = cell[0], cell[1]
        if 0 <= r < grid_size and 0 <= c < grid_size:
            grid[r][c] = 1
    return grid


def build_modules(items, trays) -> list[dict]:
    """Build each module's CAD and compute its grid footprint.

    Returns a list of dicts with keys: id, type, w, h, cad.
    The CAD is pre-shifted so its bbox starts at (0, 0, 0), ready to translate.
    """
    modules: list[dict] = []
    next_id = 1

    if items.pens > 0:
        rows = pen_rows(items.pens)
        cad = make_pen_holder(num_pens=items.pens, num_rows=rows)
        cad = _to_positive_octant(cad)
        w, h = _bbox_cells(cad)
        modules.append({"id": next_id, "type": "pen", "w": w, "h": h, "cad": cad})
        next_id += 1

    if items.standardSD + items.microSD > 0:
        cad = make_sd_holder(
            num_small_slots=items.microSD,
            num_large_slots=items.standardSD,
        )
        cad = _to_positive_octant(cad)
        w, h = _bbox_cells(cad)
        modules.append({"id": next_id, "type": "sd", "w": w, "h": h, "cad": cad})
        next_id += 1

    for tray in trays:
        height_mm = TRAY_HEIGHT_MM.get(tray.height, 30)
        units_z = max(3, int(height_mm / 10))
        cad, _ = storage_tray(
            unitsX=tray.length, unitsY=tray.width, unitsZ=units_z
        )
        cad = _to_positive_octant(cad)
        w, h = _bbox_cells(cad)
        modules.append({"id": next_id, "type": "tray", "w": w, "h": h, "cad": cad})
        next_id += 1

    return modules


def _rotate_90(cad: cq.Workplane) -> cq.Workplane:
    rotated = cad.rotate((0, 0, 0), (0, 0, 1), 90)
    return _to_positive_octant(rotated)


def position_modules(modules: list[dict], placements: list[dict]) -> list[dict]:
    """Translate each module's CAD to its placed grid position.

    Returns a list of dicts: {id, type, placement, cad}.
    """
    by_id = {m["id"]: m for m in modules}
    positioned: list[dict] = []

    for p in placements:
        m = by_id[p["id"]]
        cad = m["cad"]

        # If algorithm rotated the module, rotate the CAD 90° around Z.
        if (p["w"], p["h"]) != (m["w"], m["h"]):
            cad = _rotate_90(cad)

        # Algorithm (x=row, y=col) -> CAD (cad_x=col*10, cad_y=row*10).
        cad_x = p["y"] * CELL_MM
        cad_y = p["x"] * CELL_MM
        cad = cad.translate((cad_x, cad_y, 0))

        positioned.append({
            "id": m["id"],
            "type": m["type"],
            "placement": p,
            "cad": cad,
        })

    return positioned


def combine(positioned: list[dict]) -> cq.Workplane | None:
    combined = None
    for entry in positioned:
        combined = entry["cad"] if combined is None else combined.union(entry["cad"])
    return combined


def run_pipeline(items, trays, available_space) -> dict:
    modules = build_modules(items, trays)
    space = build_space(available_space)

    module_list = [
        {"id": m["id"], "type": m["type"], "w": m["w"], "h": m["h"]}
        for m in modules
    ]
    placements = generate_layout(space, module_list)

    positioned = position_modules(modules, placements)
    combined = combine(positioned)

    return {
        "placements": placements,
        "modules": positioned,
        "combined": combined,
        "unplaced_ids": [
            m["id"] for m in modules
            if m["id"] not in {p["id"] for p in placements}
        ],
    }
