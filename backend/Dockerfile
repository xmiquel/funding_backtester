FROM python:3.12-slim AS builder
RUN pip install uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --all-extras

FROM python:3.12-slim
WORKDIR /app/backend
RUN mkdir -p /app/.git
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /app/backend/.venv /app/backend/.venv
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src/ src/
COPY backend/tests/ tests/
COPY analytics/ /app/analytics/
ENV PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "funding_backtester.main:app", "--host", "0.0.0.0", "--port", "8000"]
