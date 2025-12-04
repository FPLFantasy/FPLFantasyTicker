# Start with the official Python image
FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Streamlit application files
COPY . .

# 🟢 CRITICAL STEP: Replace Streamlit's default index.html 🟢
# The path is now correctly set to python3.13/
# Line 1: Delete the old index.html
RUN find /usr/local/lib/python3.13/site-packages/streamlit/static/ -name 'index.html' -delete

# Line 2: Copy your new index.html with the Meta Tag
COPY index.html /usr/local/lib/python3.13/site-packages/streamlit/static/index.html

# Expose the port Streamlit will run on
EXPOSE 8501

# Command to run the application (same as your Procfile)
CMD ["streamlit", "run", "ticker_app_v13.py", "--server.port=8501", "--server.address=0.0.0.0"]
