FROM python:3.12-slim

WORKDIR /app

# Create non-root user (UID 1000) or use existing if it exists
RUN if ! getent passwd 1000 > /dev/null 2>&1; then \
        useradd -m -u 1000 fastapi; \
    else \
        echo "Using existing user with UID 1000"; \
    fi && \
    chown -R 1000:1000 /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create uploads and sessions directories with proper permissions
RUN mkdir -p /app/uploads /app/sessions && \
    chown -R 1000:1000 /app/uploads /app/sessions && \
    chmod -R 755 /app/uploads /app/sessions

# Install util-linux for runuser (user switching)
RUN apt-get update && \
    apt-get install -y --no-install-recommends util-linux && \
    rm -rf /var/lib/apt/lists/*

# Copy entrypoint script and make it executable
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

# Entrypoint runs as root to fix permissions, then switches to user 1000
ENTRYPOINT ["/docker-entrypoint.sh"]

# Default command (entrypoint will switch to user 1000)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
