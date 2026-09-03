"""HTTP client for external YOLO detection services.

This module intentionally does not own camera capture, ROS state, or robot
motion. Callers provide an RGB/BGR image and receive normalized detections.
It supports both ABot-style JSON/base64 services and the multipart endpoint
used by sample_arm.py.
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
class Detection:
    """Normalized object detection result."""

    label: str
    score: float
    bbox: list[float]
    center: Optional[list[float]] = None
    raw: dict[str, Any] = field(default_factory=dict)


class YoloSDK:
    """Client for external YOLO services.

    Parameters
    ----------
    url
        External service endpoint.
    request_format
        ``json`` for ABot-style ``POST /detect`` with base64 image,
        ``multipart`` for sample_arm-style image upload, or ``auto``.
    timeout
        HTTP timeout in seconds.
    threshold
        Default confidence threshold.
    topk
        Default maximum number of detections requested from multipart services.
    """

    def __init__(
        self,
        url: str,
        *,
        request_format: RequestFormat = "auto",
        timeout: float = 10.0,
        threshold: float = 0.25,
        topk: int = 50,
        iou_threshold: float = 0.45,
        image_ext: str = ".jpg",
    ) -> None:
        self.url = url
        self.request_format = request_format
        self.timeout = timeout
        self.threshold = threshold
        self.topk = topk
        self.iou_threshold = iou_threshold
        self.image_ext = image_ext

    def detect(
        self,
        image: Any,
        target_name: Optional[str] = None,
        *,
        threshold: Optional[float] = None,
        topk: Optional[int] = None,
    ) -> list[Detection]:
        """Detect objects in an image."""

        fmt = self._resolve_format()
        if fmt == "multipart":
            data = self._detect_multipart(image, target_name, threshold=threshold, topk=topk)
        else:
            data = self._detect_json(image, threshold=threshold)
        return self._parse_detections(data, target_name=target_name)

    def exists(
        self,
        image: Any,
        target_name: str,
        *,
        threshold: Optional[float] = None,
    ) -> bool:
        """Return whether at least one matching detection exists."""

        detections = self.detect(image, target_name=target_name, threshold=threshold)
        min_score = self.threshold if threshold is None else threshold
        return any(det.score >= min_score for det in detections)

    def _resolve_format(self) -> Literal["json", "multipart"]:
        if self.request_format in ("json", "multipart"):
            return self.request_format
        return "multipart" if "upload" in self.url else "json"

    def _detect_json(self, image: Any, *, threshold: Optional[float]) -> dict[str, Any]:
        image_b64 = _encode_image_base64(image, ext=self.image_ext)
        payload = {
            "image": image_b64,
            "conf_thres": self.threshold if threshold is None else threshold,
            "iou_thres": self.iou_threshold,
        }
        response = requests.post(self.url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _detect_multipart(
        self,
        image: Any,
        target_name: Optional[str],
        *,
        threshold: Optional[float],
        topk: Optional[int],
    ) -> dict[str, Any]:
        image_bytes, mime = _encode_image_bytes(image, ext=self.image_ext)
        files = {"image": (f"image{self.image_ext}", image_bytes, mime)}
        data = {
            "text": target_name or "",
            "topk": str(self.topk if topk is None else topk),
            "threshold": str(self.threshold if threshold is None else threshold),
            "use_amp": "false",
        }
        response = requests.post(self.url, files=files, data=data, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _parse_detections(data: dict[str, Any], *, target_name: Optional[str]) -> list[Detection]:
        if "detections" in data:
            return [_detection_from_dict(item, target_name=target_name) for item in data.get("detections", [])]

        if "bboxes" in data:
            bboxes = data.get("bboxes", []) or []
            scores = data.get("scores", []) or []
            labels = data.get("labels") or data.get("class_names") or []
            out: list[Detection] = []
            for idx, bbox in enumerate(bboxes):
                label = _value_at(labels, idx, target_name or "object")
                score = float(_value_at(scores, idx, 0.0))
                out.append(
                    Detection(
                        label=str(label),
                        score=score,
                        bbox=[float(x) for x in bbox],
                        center=_bbox_center(bbox),
                        raw={"index": idx, "source": data},
                    )
                )
            return out

        if "bbox" in data:
            bbox = data.get("bbox") or []
            score = float(data.get("score", 0.0))
            label = str(data.get("label") or target_name or "object")
            center = data.get("center") or _bbox_center(bbox)
            return [
                Detection(
                    label=label,
                    score=score,
                    bbox=[float(x) for x in bbox],
                    center=[float(x) for x in center] if center else None,
                    raw=data,
                )
            ]

        return []


def _detection_from_dict(item: dict[str, Any], *, target_name: Optional[str]) -> Detection:
    bbox = item.get("bbox")
    if bbox is None:
        bbox = [item.get("x1", 0.0), item.get("y1", 0.0), item.get("x2", 0.0), item.get("y2", 0.0)]
    label = item.get("class_name") or item.get("label") or target_name or "object"
    score = item.get("confidence", item.get("score", 0.0))
    center = item.get("center") or _bbox_center(bbox)
    return Detection(
        label=str(label),
        score=float(score),
        bbox=[float(x) for x in bbox],
        center=[float(x) for x in center] if center else None,
        raw=item,
    )


def _encode_image_base64(image: Any, *, ext: str) -> str:
    image_bytes, _ = _encode_image_bytes(image, ext=ext)
    return base64.b64encode(image_bytes).decode("utf-8")


def _encode_image_bytes(image: Any, *, ext: str) -> tuple[bytes, str]:
    if isinstance(image, bytes):
        mime = "image/png" if ext.lower() == ".png" else "image/jpeg"
        return image, mime

    if isinstance(image, (str, Path)):
        path = Path(image)
        suffix = path.suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/jpeg"
        return path.read_bytes(), mime

    arr = np.asarray(image)
    ok, buf = cv2.imencode(ext, arr)
    if not ok:
        raise ValueError(f"Failed to encode image as {ext}")
    mime = "image/png" if ext.lower() == ".png" else "image/jpeg"
    return buf.tobytes(), mime


def _bbox_center(bbox: Any) -> Optional[list[float]]:
    if bbox is None or len(bbox) != 4:
        return None
    x1, y1, x2, y2 = [float(x) for x in bbox]
    return [(x1 + x2) / 2.0, (y1 + y2) / 2.0]


def _value_at(values: Any, index: int, default: Any) -> Any:
    try:
        return values[index]
    except Exception:
        return default
