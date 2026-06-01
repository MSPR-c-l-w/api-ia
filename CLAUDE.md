# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (dev)
pip install -r requirements-dev.txt
make setup-hooks          # install pre-commit + pre-push git hooks

# Run
python run.py             # dev server on :8000
make docker-run           # full stack via docker compose (MongoDB embedded in image)

# Test
pytest                                            # all tests
pytest -m "not integration and not e2e"           # unit tests only
pytest tests/test_recommendation_engine.py        # single file
pytest tests/test_recommendation_engine.py::test_score_exercise_returns_between_zero_and_one  # single test
make test-unit                                    # unit tests + coverage report

# Quality
ruff check .              # lint
ruff format .             # format
ruff check --fix .        # lint with auto-fix

# Utilities
python scripts/export_openapi.py   # regenerate openapi.json (commit after route/schema changes)
python scripts/seed_mongodb.py     # seed MongoDB with sample data
```

## Architecture

Flask 3 + Hypercorn (ASGI) + Motor (async MongoDB). The ASGI wrapper `_LifespanAsgiApp` in `app/main.py` defers the Motor client creation to the ASGI lifespan `startup` event — this is intentional to bind Motor to Hypercorn's event loop, not a throwaway `asyncio.run()` loop.

**Bounded contexts** under `app/contexts/`:

| Context | Purpose |
|---|---|
| `workout/` | Weekly training program generation, feedback scoring, fitness profile |
| `nutrition/` | Meal analysis via vision/LLM providers, meal plan generation |

Each context has the same four-layer structure:

```
domain/          # Pure Python — entities, value objects, services, Protocol repos. No Flask/Motor.
application/     # One file = one use case. execute() raises ApplicationError, never HTTPException.
infrastructure/  # Implements domain Protocol repos (Mongo). Calls external APIs.
presentation/    # Pydantic DTOs (request/response schemas).
```

**Composition root** — `app/composition/container.py` is the only place where use cases and infrastructure adapters are wired together. Accessed via `get_container()` (LRU-cached singleton). All routers call `get_container().<use_case>.execute(payload)`.

**Legacy paths** — `app/models/`, `app/services/`, `app/data/` are re-export shims for backward compatibility. Do not add new logic there; import from `app/contexts/...` instead.

## Key patterns

**Adding a route:**
1. Create/extend entities and `Protocol` ports in `domain/`
2. Add a use case in `application/use_cases/` with a single `async def execute()` method
3. Implement infrastructure adapters if needed
4. Wire in `Container.__init__()`
5. Add a Blueprint route in `app/routers/` using `parse_json()`, `model_response()`, `@map_application_errors`

**Router anatomy:**
```python
@bp.post("/path")
@require_api_key          # validates X-API-Key header against settings.backend_api_key
@map_application_errors   # converts ApplicationError subclasses → JSON error responses
async def handler():
    payload = parse_json(RequestSchema)          # Pydantic validation, raises 422 on failure
    result = await get_container().use_case.execute(payload)
    return model_response(result)                # serialises with by_alias=True (camelCase)
```

**Error handling:** Use cases raise `ApplicationError` subclasses (defined in `app/shared/application/exceptions.py`). The `@map_application_errors` decorator maps them to HTTP status codes via `_STATUS_BY_ERROR`. To add a new error: subclass `ApplicationError`, add it to that dict.

**Testing without MongoDB:** `ENVIRONMENT=test` (set in `tests/conftest.py`) sets `settings.skip_mongodb_on_startup = True`, which skips Motor client creation in the ASGI lifespan and puts `Container` in test mode. All existing tests run without a live MongoDB.

**pytest markers:** `@pytest.mark.integration` for tests requiring a live MongoDB, `@pytest.mark.e2e` for full-stack tests. Unmarked tests are treated as unit tests.

## Settings

All config via `app/config.py` (`pydantic-settings`, reads `.env`). Notable fields:

| Setting | Default | Notes |
|---|---|---|
| `backend_api_key` | `change-me` | Must match `WORKOUT_SERVICE_API_KEY` on the NestJS backend |
| `mongodb_uri` | `mongodb://localhost:27017/healthai_coach` | Defaults to embedded MongoDB in the Docker image |
| `nutrition_google_vision_*` | `None` | Vision analysis degrades gracefully to static lookup when unset |
| `nutrition_llm_*` | `None` | LLM features silently no-op when unset |
| `backend_url` | `http://localhost:3001` | Used by `BackendNutritionLookupService`; falls back to static table on connection failure |
