FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-tk python3-pytest xvfb x11-utils openbox xdotool scrot \
    && rm -rf /var/lib/apt/lists/*
COPY desktop-session.py /opt/gar/desktop-session.py
ENV DISPLAY=:99 HOME=/tmp/home PYTHONDONTWRITEBYTECODE=1
USER 65534:65534
ENTRYPOINT ["python3", "-I", "/opt/gar/desktop-session.py"]
