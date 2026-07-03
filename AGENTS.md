# Code Review Rules — funding_backtester

## Project Overview

Full-stack funding backtesting platform.
- **Backend**: Python 3.12+, FastAPI, SQLAlchemy async + asyncpg, Pydantic v2, Alembic
- **Frontend**: React 19 + TypeScript (strict), Vite 6, Tailwind CSS, shadcn/ui, TanStack Query, Zustand

## Commands

- **Backend tests** (root: `backend/`): `uv run pytest` or `uv run pytest tests/path/to/test.py -v`
- **Backend lint**: `uv run ruff check . && uv run mypy src/`
- **Backend format**: `uv run ruff format .`
- **Frontend tests**: `pnpm --filter frontend test` or `pnpm --filter frontent exec vitest run`
- **Frontend lint**: `pnpm --filter frontend exec eslint src/`
- **Frontend typecheck**: `pnpm --filter frontend exec tsc -b --noEmit`

---

## Backend (Python / FastAPI)

### General
- Python 3.12+ features preferred (generics syntax `list[str]`, type union `X | Y`, `match`)
- `ruff` config enforces: E, F, I, N, W, UP, B, SIM — line length 100
- `mypy strict` is mandatory — no `# type: ignore` without a documented reason
- Absolute imports from `funding_backtester.*` — no relative imports

### FastAPI
- Use `APIRouter(prefix=...)` for versioned endpoints — never decorate `app.get` outside `main.py`
- All endpoints are async — `async def` with `await` for DB/calls
- Lifespan handler for startup/shutdown — no `@app.on_event` decorators
- Dependency injection via `Depends()` — never instantiate services inside handlers
- Pydantic v2 models for request/response schemas — use `model_validator` over `@validator`

### Database
- SQLAlchemy async exclusively — no sync sessions or `run_sync` unless unavoidable
- AsyncSession via `async_sessionmaker` — never raw `session.execute()` outside repository/service layer
- Alembic for migrations — never `Base.metadata.create_all` in production paths
- Use `selectinload` for relationships — avoid `lazy="subquery"` and `lazy="joined"`

### Testing
- pytest + pytest-asyncio — all test functions must be `async def` with `@pytest.mark.asyncio`
- httpx `AsyncClient` with `ASGITransport` for integration tests — never hit a real server
- 80% coverage minimum — `pytest-cov` enforced in CI
- Use pytest-asyncio fixtures for DB session — never mock SQLAlchemy at the engine level
- Bandit checks enabled for security scanning

### API Design
- RESTful resource naming: `/api/v1/resources/{id}` — no verbs in URLs
- Consistent error responses via Pydantic error schemas — no plain dict returns
- Input validation on the boundary (Pydantic + FastAPI validation) — never inside business logic

---

## Frontend (TypeScript / React)

### General
- TypeScript strict mode — `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`
- No `any` — use `unknown` and narrow with type guards when API response shape is uncertain
- Path alias `@/` maps to `src/` — always use `@/components/...`, `@/lib/...`, not relative `../../`
- Prefer named exports over default exports — only exception is `@/routes/index.tsx` for React Router

### React 19
- Functional components with hooks — no class components
- Use `use(Promise)` from React 19 and `<Suspense>` for data-fetching boundaries
- Error boundaries at route level — not per-component
- Components under `src/routes/` are page-level — keep them thin, compose from `src/components/`

### State & Data
- **TanStack Query** for server state (API data) — never store API responses in Zustand
- **Zustand** for client-only state (UI state, form state, transient data)
- Mutations via `useMutation` with optimistic updates where latency matters
- Query keys as const tuples — no string literals scattered across files

### Styling
- Tailwind CSS utility classes only — no inline styles, no CSS-in-JS, no CSS modules
- Use shadcn/ui primitives from `src/components/ui/` — never wrap them with another abstraction layer
- Design system tokens via `tailwind.config.ts` — no hardcoded colors, spacing, or font sizes
- `cn()` utility from `@/lib/utils` for conditional class merging

### Routing
- React Router v7 with `createBrowserRouter` or `<Routes>` + `<Route>` — no `reach-router` or legacy patterns
- Route-level code splitting via `lazy()` + `<Suspense>` — no bundle-size exceptions without documented tradeoff

### Testing
- Vitest + @testing-library/react — render components with `render()`, assert with `screen`
- Test behavior, not implementation — no testing of internal state, refs, or prop drilling
- Mock API calls at the network layer (`msw` or vitest mocks on `axios`) — never mock TanStack Query hooks
- Test error states, loading states, and empty states — not just the happy path
