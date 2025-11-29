FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port (not required but recommended)
EXPOSE 8000

CMD ["streamlit", "run", "ticker_app_v13.py", "--server.port", "8000", "--server.address", "0.0.0.0"]
