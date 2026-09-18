FROM python:3.11-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir build && python -m build --wheel

FROM python:3.11-slim AS runtime
RUN groupadd --system --gid 1000 appuser && useradd --system --uid 1000 --gid 1000 --create-home appuser
WORKDIR /app
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl
COPY docker/ /app/docker/
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 CMD python /app/docker/healthcheck.py
ENTRYPOINT ["autoincc-mcp"]
