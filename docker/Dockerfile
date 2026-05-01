FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    XDG_CACHE_HOME=/tmp \
    PY4WEB_PASSWORD=phuegoweb

WORKDIR /opt/py4web

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gfortran \
        libxml2 \
        libglpk-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY docker/requirements-phuegoweb.txt /tmp/requirements-phuegoweb.txt

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir -r /tmp/requirements-phuegoweb.txt

COPY . ./apps/phuEGOweb

RUN rm -rf \
      apps/phuEGOweb/support_data \
      apps/phuEGOweb/results \
      apps/phuEGOweb/databases \
      apps/phuEGOweb/uploads \
      apps/phuEGOweb/__pycache__ \
      apps/phuEGOweb/static/js/node_modules \
    && mkdir -p \
      apps/phuEGOweb/support_data \
      apps/phuEGOweb/results \
      apps/phuEGOweb/databases \
      apps/phuEGOweb/uploads \
      /tmp/matplotlib \
    && touch apps/__init__.py

EXPOSE 8000

CMD ["py4web", "run", "--host", "0.0.0.0", "--port", "8000", "--watch", "off", "apps"]
