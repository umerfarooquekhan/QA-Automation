# 0001: Core decisions

Status: accepted

## Stack
- One Python backend: FastAPI, Playwright, LangGraph, PostgreSQL.
- LLM access goes through our own provider abstraction. DeepSeek is the first provider.
- No extra infrastructure (no Redis, Celery, vector or graph database) without a demonstrated need.

## Credentials and secrets
- Credentials are kept in an encrypted file-based SecretStore outside the database.
- Credentials never appear in database records, LLM prompts, logs or artifacts.

## Human intervention
- A HumanControl abstraction hides how a person takes over the browser.
- First implementation: a headed local browser. Remote streaming may be added later.

## Vision
- DeepSeek vision is tested early (Milestone 3) on real screenshots.
- We decide afterwards whether an alternative vision provider is needed.

## Network guard
- Non-GET requests are blocked by default.
- GET requests are not assumed to be safe: they are classified, recorded, and
  state-changing patterns are blocked.

## Working method
- Implementation is incremental. One small step, then run, review, and confirm before the next.
- Phase 2 (test execution, pass/fail, bug diagnosis) is excluded.