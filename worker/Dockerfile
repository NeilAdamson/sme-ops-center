FROM python:3.12-slim

WORKDIR /app

# Create non-root user (UID 1000) or use existing if it exists
RUN if ! getent passwd 1000 > /dev/null 2>&1; then \
        useradd -m -u 1000 worker; \
    else \
        echo "Using existing user with UID 1000"; \
    fi && \
    chown -R 1000:1000 /app

# Install dependencies (skip if empty)
COPY requirements.txt .
RUN if [ -s requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Copy application
COPY . .

# Switch to non-root user
USER 1000

CMD ["python", "worker.py"]
