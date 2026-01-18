FROM python:3.12-slim

WORKDIR /app

# Create non-root user (UID 1000) or use existing if it exists
RUN if ! getent passwd 1000 > /dev/null 2>&1; then \
        useradd -m -u 1000 streamlit; \
    else \
        echo "Using existing user with UID 1000"; \
    fi && \
    chown -R 1000:1000 /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Switch to non-root user
USER 1000

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
