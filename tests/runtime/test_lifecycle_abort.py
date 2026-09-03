import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from runtime.config import ModeConfig, ModeSystemConfig
from runtime.hook import (
    LifecycleHook,
    LifecycleHookAbortError,
    LifecycleHookType,
    execute_lifecycle_hooks,
)


def test_execute_lifecycle_hooks_can_raise_abort_failure():
    hook = LifecycleHook(
        hook_type=LifecycleHookType.ON_STARTUP,
        handler_type="function",
        handler_config={"module_name": "test", "function": "start"},
        on_failure="abort",
    )
    handler = AsyncMock()
    handler.execute.return_value = False

    with (
        patch("runtime.hook.create_hook_handler", return_value=handler),
        pytest.raises(LifecycleHookAbortError, match="abort policy"),
    ):
        asyncio.run(
            execute_lifecycle_hooks(
                [hook],
                LifecycleHookType.ON_STARTUP,
                raise_on_abort=True,
            )
        )


def test_mode_config_forwards_raise_on_abort():
    mode = SimpleNamespace(
        name="nav",
        display_name="Navigation",
        description="Mid360 navigation",
        lifecycle_hooks=[],
    )

    with patch("runtime.config.execute_lifecycle_hooks", new=AsyncMock(return_value=True)) as execute:
        result = asyncio.run(
            ModeConfig.execute_lifecycle_hooks(
                mode,
                LifecycleHookType.ON_STARTUP,
                {},
                raise_on_abort=True,
            )
        )

    assert result is True
    assert execute.await_args.kwargs == {"raise_on_abort": True}


def test_system_config_forwards_raise_on_abort():
    system = SimpleNamespace(name="koala", global_lifecycle_hooks=[])

    with patch("runtime.config.execute_lifecycle_hooks", new=AsyncMock(return_value=True)) as execute:
        result = asyncio.run(
            ModeSystemConfig.execute_global_lifecycle_hooks(
                system,
                LifecycleHookType.ON_STARTUP,
                {},
                raise_on_abort=True,
            )
        )

    assert result is True
    assert execute.await_args.kwargs == {"raise_on_abort": True}
