from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import subprocess
import threading

app = FastAPI()

# Start streamlit in background
def run_streamlit():
    subprocess.run([
        "streamlit", "run", "ticker_app_v13.py",
        "--server.port", "8501",
        "--server.address", "0.0.0.0"
    ])

threading.Thread(target=run_streamlit, daemon=True).start()


@app.get("/ads.txt")
def ads():
    try:
        with open("ads.txt") as f:
            return PlainTextResponse(f.read(), media_type="text/plain")
    except:
        return PlainTextResponse("ads.txt not found", status_code=404)
