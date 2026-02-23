FROM python:3.12.7-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY apps/api/pyproject.toml apps/api/pyproject.toml
RUN pip install --no-cache-dir -e apps/api

COPY apps/api apps/api
RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
