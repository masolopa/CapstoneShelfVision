FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig*.json vite.config.ts ./
COPY public ./public
COPY src ./src
RUN npm run build

FROM python:3.13-slim-bookworm AS inference
COPY backend/requirements-inference.lock.txt /tmp/requirements-inference.lock.txt
RUN python -m venv /opt/inference \
    && /opt/inference/bin/pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.6.0+cpu torchvision==0.21.0+cpu \
    && /opt/inference/bin/pip install --no-cache-dir -r /tmp/requirements-inference.lock.txt \
    && /opt/inference/bin/pip check

FROM python:3.13-slim-bookworm
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SHELFVISION_TRAIN_PYTHON=/opt/inference/bin/python \
    REGOVA_YOLO_DEVICE=cpu \
    YOLO_CONFIG_DIR=/var/lib/regova/ultralytics \
    REGOVA_TRAIN_STATUS=/var/lib/regova/storage/model-status.json \
    REGOVA_STORAGE_ROOT=/var/lib/regova/storage

COPY --from=inference /opt/inference /opt/inference
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system regova \
    && useradd --system --gid regova --no-create-home --home-dir /var/lib/regova regova \
    && install -d -o regova -g regova /var/lib/regova/storage /var/lib/regova/ultralytics

WORKDIR /srv/regova/backend
COPY backend/requirements-app.lock.txt ./
RUN pip install --no-cache-dir -r requirements-app.lock.txt && pip check
COPY backend/app ./app
COPY backend/training/__init__.py backend/training/infer_yolo.py ./training/
COPY backend/migrations/00*.sql ./migrations/
COPY backend/bootstrap_docker.py ./
COPY --from=frontend /build/dist /srv/regova/dist
RUN install -d -o regova -g regova data/training
USER regova
RUN python -c "import app.main" && /opt/inference/bin/python -c "from ultralytics import YOLO"
EXPOSE 8011
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8011"]
