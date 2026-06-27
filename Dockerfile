FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY trinity_lite ./trinity_lite

RUN pip install --no-cache-dir ".[mcp]"

CMD ["trinity-lite", "mcp", "serve"]
