FROM python:3.12.7-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
RUN pip install --no-cache-dir -e apps/worker

COPY apps/worker apps/worker
RUN chown -R appuser:appuser /app
USER appuser
CMD ["python", "-m", "celery", "-A", "omniflow_worker.main.app", "worker", "--loglevel=INFO"]
