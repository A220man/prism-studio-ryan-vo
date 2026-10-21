# Changelog

## 1.0.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-21

### Added
- FastAPI backend with health endpoints (`/health`, `/health/ready`)
- Graph API stubs (`GET /api/v1/graph`, `POST /api/v1/graph/parse`, `GET /api/v1/graph/export`)
- SQLite database with SQLAlchemy async ORM
- React + TypeScript + Vite frontend with health dashboard
- Docker Compose stack: backend, frontend (nginx), Keycloak
- Keycloak realm import with viewer/analyst/admin roles
- GitHub Actions CI workflow (backend tests, frontend build/test, Docker builds)
- pytest backend tests with httpx/ASGI transport
- vitest frontend test scaffold
- Portfolio metadata (portfolio.json)

### Infrastructure
- Non-root Dockerfiles with healthchecks
- .env.example with all configuration options
- .gitignore excluding venv, node_modules, databases, agent metadata
- MIT LICENSE with author attribution