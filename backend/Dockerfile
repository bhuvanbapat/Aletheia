# SentinelOps backend — synthetic-environment demo image
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" sqlalchemy pydantic pydantic-settings httpx

COPY app ./app

# non-root user
RUN useradd --create-home sentinel && chown -R sentinel /app
USER sentinel

EXPOSE 8000

ENV SENTINELOPS_DATABASE_URL="sqlite:///./sentinelops.db"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
