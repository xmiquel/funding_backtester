## Description

<!-- Briefly describe the change and why it's needed. -->

Closes #

## Type of Change

- [ ] Bug fix (non-breaking)
- [ ] Feature (non-breaking)
- [ ] Breaking change
- [ ] Refactor / performance
- [ ] Documentation
- [ ] CI / infrastructure

## Quality Checklist

### Backend (if changed)
- [ ] Ruff passes: `uv run ruff check src/ tests/`
- [ ] Ruff format: `uv run ruff format --check src/ tests/`
- [ ] Mypy passes: `uv run mypy src/`
- [ ] Tests pass: `uv run pytest --cov`
- [ ] New code has tests (≥80% coverage)

### Frontend (if changed)
- [ ] TypeScript: `pnpm tsc --noEmit` passes
- [ ] Lint: `pnpm lint` passes
- [ ] Tests: `pnpm test` passes
- [ ] Prettier: `pnpm format:check` passes

### General
- [ ] No `any`, `// type: ignore`, or `# type: ignore` without documented reason
- [ ] No hardcoded secrets, tokens, or credentials
- [ ] PR is focused on a single concern (split if too large)
