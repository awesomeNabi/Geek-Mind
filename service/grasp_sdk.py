"""HTTP client for external AnyGrasp/GraspNet-style services.

The client consumes RGB-D frames supplied by OM1 providers and returns
normalized grasp candidates. It does not capture camera frames or command the
robot directly.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import cv2
import numpy as np
import requests

RequestFormat = Literal["auto", "json", "multipart"]


@dataclass
class GraspCandidate:
    """Normalized grasp candidate from an external service."""

    score: float
    width: float
    translation_camera: list[float]
    rotation_camera: Optional[list[list[float]]] = None
    translation_camera_retreat: Optional[list[float]] = None
    quaternion_camera_xyzw: Optional[list[float]] = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraspResult:
    """Grasp candidates for one detected object instance."""

    label: str
    confidence: float
    bbox: list[float]
    grasps: list[GraspCandidate]
    raw: dict[str, Any] = field(default_factory=dict)


class GraspSDK:
    """Client for external grasp-pose services.

    ``json`` mode matches ABot-style ``POST /grasp/detect``:
    RGB base64, depth PNG base64, camera intrinsics, target name.

    ``multipart`` mode matches the integrated endpoint used by sample_arm.py:
    RGB/depth files plus form fields, returning ``grasp_results.best_grasp``.
    """

    def __init__(
        self,
        url: str,
        *,
        request_format: RequestFormat = "auto",
        timeout: float = 120.0,
        top_k: int = 5,
        yolo_topk: int = 100,
        yolo_threshold: float = 0.15,
        grasp_top_k: int = 50,
        num_point: int = 20000,
        collision_thresh: float = 0.01,
    ) -> None:
        self.url = url
        self.request_format = request_format
        self.timeout = timeout
        self.top_k = top_k
        self.yolo_topk = yolo_topk
        self.yolo_threshold = yolo_threshold
        self.grasp_top_k = grasp_top_k
        self.num_point = num_point
        self.collision_thresh = collision_thresh

    def get_grasp_pose(
        self,
        color_image: Any,
        depth_image: Any,
        camera_intrinsics: Any,
        target_name: str,
        *,
        top_k: Optional[int] = None,
    ) -> list[GraspResult]:
        """Request grasp candidates for ``target_name``."""

        fmt = self._resolve_format()
        if fmt == "multipart":
            data = self._detect_multipart(color_image, depth_image, target_name)
        else:
            data = self._detect_json(color_image, depth_image, camera_intrinsics, target_name, top_k=top_k)
        return self._parse_results(data, target_name=target_name)

    def best_grasp(
        self,
        color_image: Any,
        depth_image: Any,
        camera_intrinsics: Any,
        target_name: str,
        *,
        top_k: Optional[int] = None,
    ) -> Optional[GraspCandidate]:
        """Return the highest-score grasp candidate, if any."""

        results = self.get_grasp_pose(
            color_image=color_image,
            depth_image=depth_image,
            camera_intrinsics=camera_intrinsics,
            target_name=target_name,
            top_k=top_k,
        )
        candidates = [grasp for result in results for grasp in result.grasps]
        if not candidates:
            return None
        return max(candidates, key=lambda grasp: grasp.score)

    def _resolve_format(self) -> Literal["json", "multipart"]:
        if self.request_format in ("json", "multipart"):
            return self.request_format
        return "multipart" if "integrated" in self.url else "json"

    def _detect_json(
        self,
        color_image: Any,
        depth_image: Any,
        camera_intrinsics: Any,
        target_name: str,
        *,
        top_k: Optional[int],
    ) -> dict[str, Any]:
        payload = {
            "color_image": _encode_color_rgb_base64(color_image),
            "depth_image": _encode_depth_png_base64(depth_image),
            "camera_intrinsics": _intrinsics_matrix(camera_intrinsics),
            "object_name": target_name,
            "top_k": self.top_k if top_k is None else top_k,
        }
        response = requests.post(self.url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _detect_multipart(self, color_image: Any, depth_image: Any, target_name: str) -> dict[str, Any]:
        rgb_bytes = _encode_color_png_bytes(color_image)
        depth_bytes = _encode_depth_png_bytes(depth_image)
        files = {
            "rgb_image": ("rgb.png", rgb_bytes, "image/png"),
            "depth_image": ("depth.png", depth_bytes, "application/octet-stream"),
        }
        data = {
            "text": target_name,
            "yolo_topk": str(self.yolo_topk),
            "yolo_threshold": str(self.yolo_threshold),
            "grasp_top_k": str(self.grasp_top_k),
            "use_highest_confidence": "true",
            "num_point": str(self.num_point),
            "collision_thresh": str(self.collision_thresh),
        }
        response = requests.post(self.url, files=files, data=data, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _parse_results(data: dict[str, Any], *, target_name: str) -> list[GraspResult]:
        if "results" in data:
            return [_parse_abot_result(item, target_name=target_name) for item in data.get("results", [])]

        grasp_results = data.get("grasp_results", {})
        best = grasp_results.get("best_grasp") if isinstance(grasp_results, dict) else None
        if best:
            candidate = _parse_sample_best_grasp(best)
            return [
                GraspResult(
                    label=target_name,
                    confidence=float(best.get("score", 0.0)),
                    bbox=[],
                    grasps=[candidate],
                    raw=data,
                )
            ]

        return []


def _parse_abot_result(item: dict[str, Any], *, target_name: str) -> GraspResult:
    grasps = [_parse_abot_grasp(grasp) for grasp in item.get("grasps", []) or []]
    label = str(item.get("label") or target_name)
    bbox = item.get("xyxy") or item.get("bbox") or []
    return GraspResult(
        label=label,
        confidence=float(item.get("confidence", 0.0)),
        bbox=[float(x) for x in bbox],
        grasps=grasps,
        raw=item,
    )


def _parse_abot_grasp(item: dict[str, Any]) -> GraspCandidate:
    translation = item.get("translation_camera")
    if translation is None:
        translation = item.get("translation_camera_retreat") or item.get("translation_base_retreat") or [0.0, 0.0, 0.0]
    rotation = item.get("rotation_camera") or item.get("rotation_matrix")
    return GraspCandidate(
        score=float(item.get("score", 0.0)),
        width=float(item.get("width", 0.0)),
        translation_camera=[float(x) for x in translation],
        rotation_camera=_rotation_or_none(rotation),
        translation_camera_retreat=_float_list_or_none(item.get("translation_camera_retreat")),
        quaternion_camera_xyzw=_float_list_or_none(item.get("quaternion_camera_xyzw")),
        raw=item,
    )


def _parse_sample_best_grasp(item: dict[str, Any]) -> GraspCandidate:
    translation = item.get("translation") or item.get("translation_camera") or [0.0, 0.0, 0.0]
    rotation = item.get("rotation_matrix") or item.get("rotation_camera")
    return GraspCandidate(
        score=float(item.get("score", 0.0)),
        width=float(item.get("width", 0.0)),
        translation_camera=[float(x) for x in translation],
        rotation_camera=_rotation_or_none(rotation),
        raw=item,
    )


def _encode_color_rgb_base64(image: Any) -> str:
    arr = _image_array(image)
    if arr.ndim == 3 and arr.shape[2] == 3:
        arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    ok, buf = cv2.imencode(".png", arr)
    if not ok:
        raise ValueError("Failed to encode color image")
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def _encode_color_png_bytes(image: Any) -> bytes:
    arr = _image_array(image)
    ok, buf = cv2.imencode(".png", arr)
    if not ok:
        raise ValueError("Failed to encode color image")
    return buf.tobytes()


def _encode_depth_png_base64(depth_image: Any) -> str:
    return base64.b64encode(_encode_depth_png_bytes(depth_image)).decode("utf-8")


def _encode_depth_png_bytes(depth_image: Any) -> bytes:
    if isinstance(depth_image, bytes):
        return depth_image
    if isinstance(depth_image, (str, Path)):
        return Path(depth_image).read_bytes()

    depth = np.asarray(depth_image)
    if depth.ndim == 3 and depth.shape[-1] == 1:
        depth = depth[:, :, 0]
    if depth.dtype != np.uint16:
        depth_f = depth.astype(np.float32)
        max_depth = float(np.nanmax(depth_f)) if depth_f.size else 0.0
        if max_depth <= 20.0:
            depth_f = depth_f * 1000.0
        depth = np.clip(np.nan_to_num(depth_f), 0.0, 65535.0).astype(np.uint16)

    ok, buf = cv2.imencode(".png", depth)
    if not ok:
        raise ValueError("Failed to encode depth image")
    return buf.tobytes()


def _image_array(image: Any) -> np.ndarray:
    if isinstance(image, (str, Path)):
        arr = cv2.imread(str(image), cv2.IMREAD_COLOR)
        if arr is None:
            raise ValueError(f"Failed to read image: {image}")
        return arr
    return np.asarray(image)


def _intrinsics_matrix(intrinsics: Any) -> list[list[float]]:
    if isinstance(intrinsics, dict):
        fx = float(intrinsics["fx"])
        fy = float(intrinsics["fy"])
        cx = float(intrinsics["cx"])
        cy = float(intrinsics["cy"])
        return [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]]

    matrix = np.asarray(intrinsics, dtype=float)
    if matrix.shape != (3, 3):
        raise ValueError(f"camera_intrinsics must be dict or 3x3 matrix, got {matrix.shape}")
    return matrix.tolist()


def _rotation_or_none(value: Any) -> Optional[list[list[float]]]:
    if value is None:
        return None
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != (3, 3):
        return None
    return matrix.tolist()


def _float_list_or_none(value: Any) -> Optional[list[float]]:
    if value is None:
        return None
    return [float(x) for x in value]
