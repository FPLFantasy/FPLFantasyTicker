import subprocess
import threading
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.proxy_headers import ProxyHeadersMiddleware
import httpx

app = FastAPI()
app.add_middleware(ProxyHeadersMiddleware)

# Start Streamlit on port 8501
def run_streamlit():
    subprocess.run([
        "streamlit", "run", "ticker_app_v13.py",
        "--server.port", "8501",
        "--server.address", "0.0.0.0"
    ])

threading.Thread(target=run_streamlit, daemon=True).start()

@app.get("/ads.txt")
async def ads():
    with open("ads.txt") as f:
        return PlainTextResponse(f.read(), media_type="text/plain")

@app.api_route("/{path:path}", methods=["GET", "POST"])
async def streamlit_proxy(request: Request, path: str):
    """
    Forward ALL other requests to Streamlit at http://localhost:8501
    """
    url = f"http://localhost:8501/{path}"

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.request(
            request.method,
            url,
            headers=request.headers,
            params=request.query_params
        )

    return PlainTextResponse(
        content=resp.text,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type")
    )
