# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

ast-parsing

## Roadmap

### skeleton — FastAPI + React skeleton with health endpoint

Status: done

Acceptance:
- Backend health endpoint returns 200 with version
- Frontend builds and loads
- Docker compose brings up backend + frontend
- Basic tests pass

Implementation: `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/core/database.py`, `backend/app/api/health.py`, `backend/app/api/graph.py`, `backend/tests/test_health.py`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/api/client.ts`, `frontend/src/test-setup.ts`, `frontend/src/App.test.tsx`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `compose.yaml`, `keycloak/realm.json`, `.env.example`, `.gitignore`, `portfolio.json`, `README.md`, `CHANGELOG.md`, `LICENSE`, `.github/workflows/ci.yml`

Tests: `backend/tests/test_health.py`, `frontend/src/App.test.tsx`

### ast-parsing — Deterministic AST parsing for Python files

Status: done

Acceptance:
- Parse Python files into nodes (functions, classes, imports)
- Extract edges (calls, imports, inheritance)
- Store in SQLite with pagination

Implementation: `backend/app/services/ast_parser.py`, `backend/app/models/graph.py`, `backend/app/core/database.py`, `backend/app/api/graph.py`

Tests: `backend/tests/test_ast_parser.py`, `backend/tests/test_health.py`

### graph-api — Graph query API with filtering

Status: done

Acceptance:
- Query nodes by type/name
- Query edges by type
- Export graph as JSON/GraphML

Implementation: `backend/app/api/graph.py`, `backend/app/models/graph.py`, `backend/app/core/database.py`, `frontend/src/api/client.ts`

Tests: `backend/tests/test_health.py`

### frontend-dashboard — React dashboard with graph visualization

Status: planned

Acceptance:
- File tree with parse status
- Graph view with nodes/edges
- Search and filter

### oidc-auth — Keycloak OIDC authentication

Status: planned

Acceptance:
- Login/logout flow
- Protected API endpoints
- Role-based access

### multi-language — Support for TypeScript/JavaScript, SQL, YAML

Status: planned

Acceptance:
- Parse TS/JS files
- Parse SQL schemas
- Parse YAML configs

### llm-explanations — Optional LLM-powered edge explanations

Status: planned

Acceptance:
- Configurable provider adapters
- Advisory labels on LLM output
- Grounded in actual graph data

