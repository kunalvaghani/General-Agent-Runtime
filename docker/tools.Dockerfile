FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends git libtk8.6 xvfb x11-utils \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir 'pytest>=8.4,<9'
ENV PYTHONDONTWRITEBYTECODE=1 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
WORKDIR /workspace
COPY tool-session.py /opt/gar/tool-session.py
USER 65534:65534
ENTRYPOINT ["python", "-I", "/opt/gar/tool-session.py"]
