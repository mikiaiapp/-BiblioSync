FROM python:3.13-slim

# Prevent python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Create volume mount point for persistent data (SQLite and settings)
RUN mkdir -p /data && chmod 777 /data

# Copy source code
COPY src/ /app/src/

# Expose web server port
EXPOSE 6080

# Start FastAPI server directly
CMD ["python", "src/main.py"]
