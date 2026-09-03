"""External model service clients used by OM1 robot workflows."""

from .grasp_sdk import GraspCandidate, GraspResult, GraspSDK
from .yolo_sdk import Detection, YoloSDK

__all__ = [
    "Detection",
    "GraspCandidate",
    "GraspResult",
    "GraspSDK",
    "YoloSDK",
]