# Start with the official Python image
FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Streamlit application files
COPY . .

# 🟢 CRITICAL STEP: Overwrite Streamlit's default index.html 🟢
# This line copies your new index.html (with the Meta Tag) and overwrites the existing one.
COPY index.html /usr/local/lib/python3.13/site-packages/streamlit/static/index.html

# Expose the port Streamlit will run on
EXPOSE 8501

# Command to run the application (same as your Procfile)
CMD ["streamlit", "run", "ticker_app_v13.py", "--server.port=8501", "--server.address=0.0.0.0"]
