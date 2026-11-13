FROM ghcr.io/astral-sh/uv:latest AS uv

FROM python:3.14-slim AS backend
ARG INSTALL_FFMPEG=1
RUN if [ "$INSTALL_FFMPEG" = "1" ]; then \
    apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*; \
 fi

WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY main.py create_user.py alembic.ini ./
COPY alembic/ alembic/
COPY src/ src/
RUN mkdir -p /app/logs /data
EXPOSE 8090
CMD ["sh", "-c", "alembic upgrade head && exec python main.py"]

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /frontend
COPY rzk/package.json rzk/package-lock.json ./
RUN npm ci
COPY rzk/ ./
RUN npm run build

FROM nginx:stable-alpine AS frontend
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /frontend/dist/ /usr/share/nginx/html/
