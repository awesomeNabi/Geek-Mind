"""Specify TaskNode fields omitted by MAGIC's generic plan tool schema."""

import json
from copy import deepcopy

from jsonschema import validate
from tasks.planner import PLAN_TOOL

from .contracts import SCHEMAS

MICRODUCK_PLAN_TOOL = deepcopy(PLAN_TOOL)
MICRODUCK_PLAN_TOOL["function"]["parameters"]["properties"]["nodes"].update(
    maxItems=12,
    items={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "node_id": {"type": "string", "minLength": 1, "maxLength": 80},
            "skill": {"type": "string", "enum": list(SCHEMAS)},
            "arguments": {"type": "object"},
            "depends_on": {"type": "array", "items": {"type": "string"}},
            "verifier": {"type": "string", "enum": ["microduck_observation"]},
        },
        "required": ["node_id", "skill", "arguments", "depends_on", "verifier"],
    },
)


class StructuredPlanClient:
    """Keep MAGIC's planner and LLM; tighten the plan schema at the API boundary."""

    def __init__(self, client, goal, image=None):
        self.client, self.image = client, image
        self.function_schemas = client.function_schemas
        self.tool = deepcopy(MICRODUCK_PLAN_TOOL)
        self.tool["function"]["parameters"]["properties"]["goal"] = {
            "type": "string",
            "enum": [goal],
            "description": "Copy the original user goal exactly, including punctuation. Do not rephrase.",
        }

    async def ask(self, prompt):
        original = self.client.function_schemas
        self.client.function_schemas = [self.tool]
        kwargs = {}
        if self.image:
            kwargs["messages"] = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Current robot head camera for grounded planning."},
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/jpeg;base64," + self.image},
                        },
                    ],
                }
            ]
        try:
            result = await self.client.ask(prompt, **kwargs)
            for action in getattr(result, "actions", ()):
                if action.type == "propose_task_plan":
                    validate(json.loads(action.value), self.tool["function"]["parameters"])
            return result
        finally:
            self.client.function_schemas = original
