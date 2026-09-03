# Repository Guidelines

## Project Structure & Module Organization

OM1 is a Python robotics and agent runtime. Core runtime code lives in `src/`, with plugins grouped by capability: `src/actions/`, `src/inputs/`, `src/backgrounds/`, `src/providers/`, `src/llm/`, and `src/runtime/`. Agent and robot configuration files are in `config/`, including JSON5 examples and schemas under `config/schema/`. Tests mirror the source layout in `tests/`; hardware-oriented checks live in `system_hw_test/` and are excluded from default pytest runs. Documentation and images are in `docs/`. Service integrations and vendored or submodule-backed services are under `service/`.

## Build, Test, and Development Commands

Use `uv` for environment and dependency management.

```bash
uv venv
uv sync --all-groups
uv run src/run.py spot
uv run pytest --log-cli-level=DEBUG -s
pre-commit run --all-files
```

`uv run src/run.py spot` starts the example Spot agent. The default pytest command skips tests marked `integration` and avoids hardware subtrees. `pre-commit run --all-files` applies the repository checks before committing.

## Coding Style & Naming Conventions

Target Python 3.11+ and use 4-space indentation. Formatting is managed by Black with a 120-character line length; imports use isort's Black profile. Ruff checks `E`, `F`, and selected docstring rules, with NumPy-style docstrings preferred. Use `snake_case` for functions, modules, config keys, and tests; use `PascalCase` for classes. Keep plugin names descriptive and aligned with their directory, for example `src/actions/arm_arx_x5_yolograsp/`.

## Testing Guidelines

Use pytest for unit tests and pytest-asyncio for async code. Place tests under `tests/` with names like `test_<module>.py` and test functions named `test_<behavior>()`. Add focused tests for new actions, inputs, providers, config rules, and runtime behavior. Coverage is configured for `src/` with a 65% minimum; generated, vendored, and hardware-specific paths are excluded.

## Commit & Pull Request Guidelines

Prefer clear, conventional commit messages such as `feat: add robot action`, `fix: handle missing config`, or `docs: update setup notes`. PRs must state the problem being solved, explain design choices, link relevant issues, and include screenshots or logs when behavior changes. Discuss significant features, refactors, dependency upgrades, or style-only work in an issue before opening a PR.

## Security & Configuration Tips

Do not commit secrets, API keys, runtime state, large model checkpoints, logs, or local hardware captures. Start from `.env.example`, keep private values in `.env`, and document required config changes in `config/` or `docs/`.

## Git Status and Commit Guidance

At the end of every code modification task, check the current Git status and include a summary of uncommitted files.The remote repositories is https://github.com/awesomeNabi/MAGIC.git.

Rules:

- Always run or inspect the equivalent of `git status --short` before the final response.
- Include a `Git status` section in the final response.
- List all files that are currently modified, added, deleted, renamed, or untracked and have not been committed.
- If there are no uncommitted files, explicitly say so.
- Do not create commits automatically unless the user explicitly asks.

For important changes, ask the user whether they want a commit to be created.

Important changes include:

- Runtime behavior changes.
- API or configuration schema changes.
- New actions, inputs, providers, or runtime modules.
- Dependency changes.
- Security-related changes.
- Large refactors.
- Changes that affect tests, hardware behavior, or deployment behavior.

When asking whether to commit, provide:

1. A suggested commit message using conventional commit style.
2. A short explanation of why this change is worth committing separately.
3. A brief summary of the files that would be included.

Suggested final response format:

- Summary
- Files changed
- Tests/checks run
- Git status
- Commit suggestion, if the change is important

## Final response format

At the end, report:

1. Files changed.
2. Main changes.
3. Tests/checks run.
4. Git status, including all files that have not been committed.
5. Remaining risks.
6. Commit suggestion, if the change is important.

## Review guidelines

- Focus on serious bugs, unsafe behavior, and regressions.
- Check whether changes may break robot runtime behavior, ROS2 communication, device access, or hardware safety.
- Flag missing tests for runtime, action, input, provider, and configuration changes.
- Check whether secrets, API keys, tokens, IP addresses, or credentials are accidentally logged or committed.
- For changes under src/actions/, src/inputs/, src/providers/, src/runtime/, carefully check error handling and failure recovery.
- For config changes, verify that default values are safe and compatible with existing examples.
- For hardware-related code, flag any change that could cause uncontrolled motion, unsafe actuator commands, or missing emergency-stop handling.
- Mention files that were changed but not covered by tests.
- At the end of each review, summarize the highest-risk files and whether the PR looks safe to merge.