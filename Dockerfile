FROM python:3.11-slim

# Install system FFmpeg and certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure downloads directory exists
RUN mkdir -p downloads

ENV PORT=5000
EXPOSE 5000

# Start production server with Gunicorn (1 worker + threads to support in-memory progress tracking)
CMD ["sh", "-c", "gunicorn app:app --workers 1 --threads 8 --timeout 180 --bind 0.0.0.0:${PORT:-5000}"]
