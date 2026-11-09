"""CLI for observation, direct tools, durable plans, and MAGIC natural-language planning."""

import argparse
import asyncio
import json
from uuid import uuid4

from .client import BridgeClient
from .contracts import TERMINAL
from .settings import ROOT, STATE


def output(value):
    print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)


async def run(args):
    client = BridgeClient()
    if args.command == "state":
        output(await client.state())
    elif args.command == "stop":
        output(await client.stop())
    elif args.command == "reset":
        output(await client.request("/reset", {}))
    elif args.command == "image":
        value = await client.request("/image")
        value.pop("base64")
        output(value)
    elif args.command == "status":
        output(await client.status(args.id))
    elif args.command == "cancel":
        output(await client.cancel(args.id))
    elif args.command == "action":
        value = await client.start(args.skill, json.loads(args.arguments), args.id)
        output(value)
        if args.wait:
            try:
                while value["status"] not in TERMINAL | {"UNKNOWN"}:
                    await asyncio.sleep(0.25)
                    value = await client.status(value["command_id"])
                output(value)
            except BaseException:
                await client.cancel(value["command_id"])
                raise
            return 0 if value["status"] == "SUCCEEDED" else 1
    else:
        from .magic_runtime import Session, load_plan

        async with Session() as session:
            if args.command == "demo":
                plan = load_plan(ROOT / "config/demo-plan.json")
            elif args.command == "plan":
                plan = load_plan(args.file)
            else:
                plan = await session.propose(args.goal, args.llm_config, args.vision)
            STATE.mkdir(parents=True, exist_ok=True)
            path = STATE / f"plan-{uuid4().hex}.json"
            path.write_text(
                json.dumps(
                    {"goal": plan.goal, "nodes": [n.to_dict() for n in plan.nodes]},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            output({"plan_path": str(path), "goal": plan.goal, "nodes": [n.to_dict() for n in plan.nodes]})
            if getattr(args, "plan_only", False):
                return 0
            result = await session.execute(plan)
            output(result)
            return 0 if result["run"]["state"] == "SUCCEEDED" else 1
    return 0


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("state", "stop", "reset", "image", "demo"):
        commands.add_parser(name)
    for name in ("status", "cancel"):
        commands.add_parser(name).add_argument("id")
    action = commands.add_parser("action")
    action.add_argument("skill")
    action.add_argument("arguments", nargs="?", default="{}")
    action.add_argument("--id", default=None)
    action.add_argument("--wait", action="store_true")
    commands.add_parser("plan").add_argument("file")
    ask = commands.add_parser("ask")
    ask.add_argument("goal")
    ask.add_argument("--llm-config")
    ask.add_argument("--vision", action="store_true")
    ask.add_argument("--plan-only", action="store_true")
    try:
        code = asyncio.run(run(parser.parse_args()))
    except KeyboardInterrupt:
        code = 130
    except Exception as exc:
        print(f"Error: {exc}")
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
