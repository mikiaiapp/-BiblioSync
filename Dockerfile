FROM python:3.13-slim

# Prevent python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:1
ENV HOME=/root

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-tk \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    supervisor \
    fluxbox \
    && rm -rf /var/lib/apt/lists/*

# Create symlink so that accessing the root URL (/) redirects to the VNC page
RUN ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html

# Set working directory
WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Create volume mount point for persistent data (SQLite and settings)
RUN mkdir -p /data && chmod 777 /data

# Copy source code and supervisor config
COPY src/ /app/src/
COPY supervisord.conf /app/supervisord.conf

# Expose noVNC port
EXPOSE 6080

# Start supervisor to run virtual display and VNC components
CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]
