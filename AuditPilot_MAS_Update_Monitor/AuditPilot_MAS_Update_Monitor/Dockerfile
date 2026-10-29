FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY auditpilot ./auditpilot
RUN pip install --no-cache-dir . && useradd --create-home auditpilot && mkdir -p /app/data && chown auditpilot /app/data
USER auditpilot
EXPOSE 8000
CMD ["auditpilot", "serve", "--host", "0.0.0.0", "--db", "/app/data/auditpilot.sqlite"]
