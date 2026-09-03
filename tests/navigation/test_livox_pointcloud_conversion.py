from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import pytest

sys.dont_write_bytecode = True

BRIDGE_SRC = (
    Path(__file__).resolve().parents[2]
    / "service"
    / "unitree_native_slam"
    / "autonomy_mid360"
    / "workspace"
    / "src"
    / "mid360_go2_nav_bridge"
)
sys.path.insert(0, str(BRIDGE_SRC))

from mid360_go2_nav_bridge.pointcloud_conversion import (  # noqa: E402
    FASTLIO_POINT_STEP,
    convert_livox_cloud,
    fastlio_dtype,
)


@dataclass
class Field:
    name: str
    offset: int
    datatype: int
    count: int = 1


LIVOX_FIELDS = [
    Field("x", 0, 7),
    Field("y", 4, 7),
    Field("z", 8, 7),
    Field("intensity", 12, 7),
    Field("tag", 16, 2),
    Field("line", 17, 2),
    Field("timestamp", 18, 8),
]
LIVOX_DTYPE = np.dtype(
    {
        "names": [field.name for field in LIVOX_FIELDS],
        "formats": ["<f4", "<f4", "<f4", "<f4", "u1", "u1", "<f8"],
        "offsets": [field.offset for field in LIVOX_FIELDS],
        "itemsize": 26,
    }
)


def test_convert_livox_cloud_preserves_points_and_creates_relative_nanoseconds():
    source = np.zeros(3, dtype=LIVOX_DTYPE)
    source["x"] = [1.0, 2.0, 3.0]
    source["y"] = [-1.0, -2.0, -3.0]
    source["z"] = [0.1, 0.2, 0.3]
    source["intensity"] = [10.0, 20.0, 30.0]
    source["line"] = [0, 2, 3]
    source["timestamp"] = [1_750_000_000_000_000_000, 1_750_000_000_025_000_000, 1_750_000_000_050_000_000]

    output_bytes, span_ns = convert_livox_cloud(
        data=source.tobytes(),
        fields=LIVOX_FIELDS,
        width=3,
        height=1,
        point_step=26,
        row_step=78,
    )
    output = np.frombuffer(output_bytes, dtype=fastlio_dtype())

    assert len(output_bytes) == 3 * FASTLIO_POINT_STEP
    np.testing.assert_allclose(output["x"], source["x"])
    np.testing.assert_allclose(output["y"], source["y"])
    np.testing.assert_allclose(output["z"], source["z"])
    np.testing.assert_allclose(output["intensity"], source["intensity"])
    np.testing.assert_array_equal(output["ring"], [0, 2, 3])
    np.testing.assert_allclose(output["time"], [0.0, 25_000_000.0, 50_000_000.0], atol=512.0)
    assert span_ns == pytest.approx(50_000_000.0, abs=512.0)


def test_convert_livox_cloud_honors_row_padding():
    rows = np.zeros((2, 2), dtype=LIVOX_DTYPE)
    rows["x"] = [[1.0, 2.0], [3.0, 4.0]]
    rows["timestamp"] = [[1000.0, 2000.0], [3000.0, 4000.0]]
    padded = bytearray((2 * 26 + 8) * 2)
    padded[0:52] = rows[0].tobytes()
    padded[60:112] = rows[1].tobytes()

    output_bytes, _ = convert_livox_cloud(
        data=padded,
        fields=LIVOX_FIELDS,
        width=2,
        height=2,
        point_step=26,
        row_step=60,
    )
    output = np.frombuffer(output_bytes, dtype=fastlio_dtype())
    np.testing.assert_allclose(output["x"], [1.0, 2.0, 3.0, 4.0])


def test_convert_livox_cloud_uses_earliest_finite_timestamp():
    source = np.zeros(3, dtype=LIVOX_DTYPE)
    source["timestamp"] = [3000.0, np.nan, 1000.0]

    output_bytes, span_ns = convert_livox_cloud(
        data=source.tobytes(),
        fields=LIVOX_FIELDS,
        width=3,
        height=1,
        point_step=26,
        row_step=78,
    )
    output = np.frombuffer(output_bytes, dtype=fastlio_dtype())

    np.testing.assert_allclose(output["time"], [2000.0, 0.0, 0.0])
    assert span_ns == 2000.0


def test_convert_livox_cloud_rejects_missing_line_field():
    source = np.zeros(1, dtype=LIVOX_DTYPE)
    with pytest.raises(ValueError, match="missing fields: line"):
        convert_livox_cloud(
            data=source.tobytes(),
            fields=[field for field in LIVOX_FIELDS if field.name != "line"],
            width=1,
            height=1,
            point_step=26,
            row_step=26,
        )
