"""Bounded commands and explicit outcomes shared across the process boundary."""

import math

TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}
SKILLS = ("sit", "stand", "kick_left", "kick_right", "roulade", "ground_pick")
DIRECTIONS = ("left", "right", "up", "down", "center")


def schema(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


SCHEMAS = {
    "walk": schema({"distance_m": {"type": "number", "minimum": -2, "maximum": 2}}),
    "turn": schema({"degrees": {"type": "number", "minimum": -180, "maximum": 180}}),
    "navigate": schema({"place": {"type": "string", "minLength": 1, "maxLength": 80}}),
    "navigate_to": schema(
        {
            "x": {"type": "number", "minimum": -10, "maximum": 10},
            "y": {"type": "number", "minimum": -10, "maximum": 10},
        }
    ),
    "do_skill": schema({"skill": {"type": "string", "enum": list(SKILLS)}}),
    "look": schema({"direction": {"type": "string", "enum": list(DIRECTIONS)}}),
    "snapshot": schema({}),
}


class ControlError(Exception):
    def __init__(self, detail, code="control_error", status="FAILED"):
        super().__init__(detail)
        self.code, self.status = code, status


def validate(skill, arguments):
    if skill not in SCHEMAS or not isinstance(arguments, dict):
        raise ValueError("Unknown skill or invalid arguments")
    properties = SCHEMAS[skill]["properties"]
    if set(arguments) != set(properties):
        raise ValueError(f"{skill} requires exactly {list(properties)}")
    for key, spec in properties.items():
        value = arguments[key]
        if spec["type"] == "number":
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{key} must be a finite number")
            if not spec["minimum"] <= value <= spec["maximum"]:
                raise ValueError(f"{key} outside [{spec['minimum']}, {spec['maximum']}]")
        elif not isinstance(value, str) or not value.strip() or len(value) > 80:
            raise ValueError(f"Invalid {key}")
        if "enum" in spec and value not in spec["enum"]:
            raise ValueError(f"Invalid {key}: {value}")
