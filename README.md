# QA Agent

An AI agent that explores an unfamiliar website like a QA engineer and generates
evidence-backed test cases.

**Scope (Phase 1):** exploration, application modeling, test case generation, export.
Test execution, pass/fail evaluation and bug diagnosis are out of scope.

## Status

Milestone 1, Step 1.1: repository skeleton and tooling only.

## Development setup (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Checks

Run from the `backend` folder with the virtual environment active:

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

## Layout

- `backend/src/qa_agent/` application code, one package per component
- `backend/tests/` unit, component and integration tests
- `fixture_app/` our own test website (added in later steps)
- `docs/` architecture documents and decision records
- `data/` local runtime data (git-ignored)