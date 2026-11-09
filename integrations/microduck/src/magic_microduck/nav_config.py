"""Derive navigation parameters from Microduck without editing the upstream file."""

import yaml

from .settings import DUCK_ROOT, STATE


def main():
    source = DUCK_ROOT / "microduck_bringup/config/nav2.yaml"
    config = yaml.safe_load(source.read_text())
    controller = config["controller_server"]["ros__parameters"]
    # At 10 Hz, the upstream 4 rad/s² cap gives a 0.4 rad/s initial command,
    # below velstand's effective turning range. It never accelerates out of it.
    # Preserve the existing 1 rad/s speed limit; permit reaching it from rest.
    controller["FollowPath"]["max_angular_accel"] = 10.0
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "nav2.generated.yaml").write_text(yaml.safe_dump(config, sort_keys=False))


if __name__ == "__main__":
    main()
