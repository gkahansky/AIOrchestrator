FROM python:3.12-slim-bookworm

WORKDIR /app

# ── System deps (Python build + security tool dependencies) ───────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    fonts-noto \
    # Security scanning deps (nikto not in bookworm repos — installed via git below)
    nmap \
    perl \
    openssl \
    wget \
    curl \
    unzip \
    git \
    dnsutils \
    && rm -rf /var/lib/apt/lists/*

# ── Python packages ────────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

# ── Security scanning binaries ─────────────────────────────────────────────────
# nuclei — template-based vulnerability scanner (9,000+ templates)
ARG NUCLEI_VERSION=3.3.9
RUN wget -q "https://github.com/projectdiscovery/nuclei/releases/download/v${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION}_linux_amd64.zip" \
      -O /tmp/nuclei.zip \
    && unzip -q /tmp/nuclei.zip nuclei -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/nuclei \
    && rm /tmp/nuclei.zip

# ffuf — fast web fuzzer (path + parameter discovery)
ARG FFUF_VERSION=2.1.0
RUN wget -q "https://github.com/ffuf/ffuf/releases/download/v${FFUF_VERSION}/ffuf_${FFUF_VERSION}_linux_amd64.tar.gz" \
      -O /tmp/ffuf.tar.gz \
    && tar -xzf /tmp/ffuf.tar.gz -C /tmp/ ffuf \
    && mv /tmp/ffuf /usr/local/bin/ffuf \
    && chmod +x /usr/local/bin/ffuf \
    && rm /tmp/ffuf.tar.gz

# dalfox — XSS scanner + PoC generator
ARG DALFOX_VERSION=2.9.2
RUN wget -q "https://github.com/hahwul/dalfox/releases/download/v${DALFOX_VERSION}/dalfox_${DALFOX_VERSION}_linux_amd64.tar.gz" \
      -O /tmp/dalfox.tar.gz \
    && tar -xzf /tmp/dalfox.tar.gz -C /tmp/ \
    && mv /tmp/dalfox /usr/local/bin/dalfox \
    && chmod +x /usr/local/bin/dalfox \
    && rm /tmp/dalfox.tar.gz

# sqlmap — SQL injection detection and exploitation
RUN git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git /opt/sqlmap \
    && ln -sf /opt/sqlmap/sqlmap.py /usr/local/bin/sqlmap \
    && chmod +x /opt/sqlmap/sqlmap.py

# nikto — web server misconfiguration scanner (not in bookworm apt)
RUN git clone --depth 1 https://github.com/sullo/nikto.git /opt/nikto \
    && ln -sf /opt/nikto/program/nikto.pl /usr/local/bin/nikto \
    && chmod +x /opt/nikto/program/nikto.pl

# testssl.sh — comprehensive TLS/SSL audit
RUN wget -q "https://raw.githubusercontent.com/drwetter/testssl.sh/3.2/testssl.sh" \
      -O /usr/local/bin/testssl.sh \
    && chmod +x /usr/local/bin/testssl.sh

# Pre-fetch nuclei templates — cached in this layer (~200 MB, avoids runtime download)
RUN nuclei -update-templates -silent || true

# ── App code ───────────────────────────────────────────────────────────────────
COPY . .

# Make src importable
ENV PYTHONPATH=/app/src
# Point marketing audit pipeline at the vendored submodule
ENV AI_MARKETING_CLAUDE_PATH=/app/vendor/ai-marketing-claude

CMD ["sh", "-c", "if [ \"$SERVICE_ROLE\" = \"worker\" ]; then exec celery -A aiplatform.worker worker --loglevel=info --concurrency=2; else python -m alembic upgrade head && exec uvicorn aiplatform.webapp.main:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
