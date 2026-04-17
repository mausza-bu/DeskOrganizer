import cadquery as cq

# Geometry defaults
CELL_SIZE = 20.0        # Base unit footprint per pen (X and Y)
HOLDER_HEIGHT = 70.0    # Total height
SLOT_DIAMETER = 12.0    # Pen slot diameter
FLOOR_THICKNESS = 5.0   # Material left under slots so pens don't touch desk


def make_pen_holder(
    num_pens: int,
    num_rows: int,
    cell_size: float = CELL_SIZE,
    holder_height: float = HOLDER_HEIGHT,
    slot_diameter: float = SLOT_DIAMETER,
    floor_thickness: float = FLOOR_THICKNESS,
    export_path: str | None = None,
) -> cq.Workplane:
    """Build a rectangular pen holder with circular slots.

    E.g. num_pens=10, num_rows=2 -> 100x40x70mm block with 5x2 slots.
    """
    if num_pens % num_rows != 0:
        raise ValueError(
            f"num_pens ({num_pens}) must be divisible by num_rows ({num_rows})"
        )

    cols = num_pens // num_rows
    outer_x = cols * cell_size
    outer_y = num_rows * cell_size
    slot_depth = holder_height - floor_thickness

    result = cq.Workplane("XY").box(
        outer_x, outer_y, holder_height, centered=(False, False, False)
    )

    slot_points = [
        (col * cell_size + cell_size / 2, row * cell_size + cell_size / 2)
        for row in range(num_rows)
        for col in range(cols)
    ]

    result = (
        result.faces(">Z").workplane()
        .pushPoints(slot_points)
        .circle(slot_diameter / 2)
        .cutBlind(-slot_depth)
    )

    if export_path:
        cq.exporters.export(result, export_path)

    return result


if __name__ == "__main__":
    make_pen_holder(num_pens=10, num_rows=2, export_path="pen_holder.stl")
