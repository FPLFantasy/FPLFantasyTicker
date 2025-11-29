# Dockerfile for Streamlit app (ticker_app_v13.py)
FROM python:3.11-slim

# Set working dir
WORKDIR /app

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app code
COPY . /app

# Expose port (Railway supplies $PORT at runtime)
ENV PORT=8080
EXPOSE ${PORT}

# Use the Streamlit command binding to the host and Railway-provided port
CMD ["streamlit", "run", "ticker_app_v13.py", "--server.port", "$PORT", "--server.address", "0.0.0.0", "--server.headless", "true"]
