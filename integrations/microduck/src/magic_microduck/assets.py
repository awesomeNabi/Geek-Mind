"""Fetch a pinned official v8 walking policy into this project only."""

import hashlib
import json
import urllib.request
from uuid import uuid4

from .settings import ROOT

REVISION = "665ae4eb20bfe13bca1ef4ea6d4bb6b4a096e448"
SHA256 = "2fc7f8ee6acd7d0d3f66a99927b5d5a56589aeed02ec714de329b252d5ccf492"
URL = f"https://huggingface.co/pollen-robotics/microduck-policies/resolve/{REVISION}/velstand.onnx"


def prepare():
    directory = ROOT / ".assets"
    directory.mkdir(exist_ok=True)
    target = directory / "velstand-v8.onnx"
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != SHA256:
        with urllib.request.urlopen(URL, timeout=60) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != SHA256:
            raise RuntimeError("Official policy SHA256 mismatch; refusing to load it")
        temporary = directory / (uuid4().hex + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
    (directory / "source.json").write_text(
        json.dumps(
            {
                "url": URL,
                "revision": REVISION,
                "sha256": SHA256,
                "tag": "v8",
                "upstream": "pollen-robotics/microduck-policies",
            },
            indent=2,
        )
    )
    return target


if __name__ == "__main__":
    print(prepare())
