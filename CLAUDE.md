# hackatune

## Tooling

This repo uses **uv** for Python. Always:

- Run Python via `uv run python ...` (or `uv run <script>.py`), not bare `python`/`python3`.
- Install dependencies with `uv add <package>`, not `pip install`.
- The project targets Python 3.14 (see `.python-version`).
