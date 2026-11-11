# QA Agent

An AI agent that opens a website in a real browser, logs in with the credentials you give it,
explores the site, and writes test cases with DeepSeek. When a human is needed (OTP,
Cloudflare, CAPTCHA) it pauses and waits for you in the same browser window.

- Phase 1 (this project): generate test cases, store them in MongoDB, export JSON, CSV, TXT.
- Phase 2 (later): run the stored test cases and keep the results. Not started.

## Run the backend (Windows PowerShell)

    cd backend
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python -m uvicorn app.main:app

Open http://127.0.0.1:8000/health. Do not use --reload while a run is active: a reload
closes the browser.

## Tests

    cd backend
    python -m pytest

## Settings

Copy .env.example to .env in the project root. .env is never committed.

## Layout

- backend/app/ is the backend: main.py (API), config.py (settings), redaction.py (secret
  masking and safe logging). browser.py, explorer.py, llm.py, db.py and export.py are added
  in the step that needs each one.
- backend/tests/ holds the basic tests.
- frontend/ is React + Vite + TypeScript, added once browser login works.
- backend/data/ holds screenshots and exports (git-ignored, created by the code).

## Safety rules (Phase 1)

- Allowed: navigation, tabs, and elements that declare they open something. Opening a form
  is fine. Submitting a form or making a persistent change is never allowed.
- Everything unknown or ambiguous is skipped and reported, whatever its label says.
- A request guard blocks any non-GET request that is not an allowed read or the narrowly
  permitted login request. A blocked control is never clicked again.
- Passwords, OTPs, API keys and tokens never appear in logs or LLM prompts. You type OTP
  codes into the browser window yourself.
- Use a staging site or test account. Page text is sent to DeepSeek.

## MongoDB

- runs: one document per exploration (URL, status, pages visited, events). No credentials.
- test_cases: one document per version, _id = test_id@v<version>. Steps and expected
  results are structured so Phase 2 can run them later.
- Phase 2 will add executions and execution_results, which reference a test case by
  (test_id, version) and are never written into test_cases.