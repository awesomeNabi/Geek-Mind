"""Binary PointCloud2 conversion helpers without ROS runtime dependencies."""

from __future__ import annotations

from typing import Iterable

import numpy as np


POINT_FIELD_FORMATS = {
    1: "i1",  # INT8
    2: "u1",  # UINT8
    3: "i2",  # INT16
    4: "u2",  # UINT16
    5: "i4",  # INT32
    6: "u4",  # UINT32
    7: "f4",  # FLOAT32
    8: "f8",  # FLOAT64
}

FASTLIO_POINT_STEP = 24
FASTLIO_FIELD_LAYOUT = (
    ("x", 0, 7),
    ("y", 4, 7),
    ("z", 8, 7),
    ("intensity", 12, 7),
    ("ring", 16, 4),
    ("time", 20, 7),
)


def pointcloud_dtype(fields: Iterable[object], point_step: int, is_bigendian: bool = False) -> np.dtype:
    """Create a structured NumPy dtype from PointField-like objects."""
    names: list[str] = []
    formats: list[object] = []
    offsets: list[int] = []
    byte_order = ">" if is_bigendian else "<"

    for field in fields:
        datatype = int(field.datatype)
        if datatype not in POINT_FIELD_FORMATS:
            raise ValueError(f"unsupported PointField datatype {datatype} for {field.name}")
        count = int(field.count)
        if count < 1:
            raise ValueError(f"invalid PointField count {count} for {field.name}")
        scalar_format = byte_order + POINT_FIELD_FORMATS[datatype]
        field_format: object = scalar_format if count == 1 else (scalar_format, count)
        names.append(str(field.name))
        formats.append(field_format)
        offsets.append(int(field.offset))

    return np.dtype(
        {
            "names": names,
            "formats": formats,
            "offsets": offsets,
            "itemsize": int(point_step),
        }
    )


def fastlio_dtype() -> np.dtype:
    """Return the aligned x/y/z/intensity/ring/time layout consumed by FAST-LIO."""
    return np.dtype(
        {
            "names": [field[0] for field in FASTLIO_FIELD_LAYOUT],
            "formats": ["<f4", "<f4", "<f4", "<f4", "<u2", "<f4"],
            "offsets": [field[1] for field in FASTLIO_FIELD_LAYOUT],
            "itemsize": FASTLIO_POINT_STEP,
        }
    )


def convert_livox_cloud(
    *,
    data: bytes | bytearray | memoryview,
    fields: Iterable[object],
    width: int,
    height: int,
    point_step: int,
    row_step: int,
    is_bigendian: bool = False,
) -> tuple[bytes, float]:
    """Convert Go2 Livox x/y/z/intensity/tag/line/timestamp points for FAST-LIO.

    The Go2 publishes an absolute FLOAT64 nanosecond timestamp per point. FAST-LIO's
    Velodyne-style preprocessing expects FLOAT32 relative time and, with
    ``timestamp_unit: 3``, interprets that value as nanoseconds.
    """
    width = int(width)
    height = int(height)
    point_step = int(point_step)
    row_step = int(row_step)
    if width < 1 or height < 1:
        return b"", 0.0
    if point_step < 1 or row_step < width * point_step:
        raise ValueError("invalid PointCloud2 point_step/row_step")
    if len(data) < row_step * height:
        raise ValueError("PointCloud2 data is shorter than row_step * height")

    source_dtype = pointcloud_dtype(fields, point_step, is_bigendian)
    required = {"x", "y", "z", "intensity", "line", "timestamp"}
    missing = sorted(required.difference(source_dtype.names or ()))
    if missing:
        raise ValueError(f"Livox cloud is missing fields: {', '.join(missing)}")

    source = np.ndarray(
        shape=(height, width),
        dtype=source_dtype,
        buffer=data,
        strides=(row_step, point_step),
    ).reshape(-1)
    output = np.zeros(source.size, dtype=fastlio_dtype())
    for coordinate in ("x", "y", "z", "intensity"):
        output[coordinate] = source[coordinate].astype(np.float32, copy=False)
    output["ring"] = source["line"].astype(np.uint16, copy=False)

    timestamps = source["timestamp"].astype(np.float64, copy=False)
    finite = np.isfinite(timestamps)
    if not finite.any():
        raise ValueError("Livox cloud contains no finite timestamps")
    frame_start = float(np.min(timestamps[finite]))
    relative_ns = timestamps - frame_start
    relative_ns[~finite] = 0.0
    output["time"] = relative_ns.astype(np.float32)

    frame_span_ns = float(np.max(relative_ns[finite]))
    return output.tobytes(order="C"), frame_span_ns
