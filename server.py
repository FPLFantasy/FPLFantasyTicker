import subprocess
import threading
from fastapi import FastAPI, Request
from fastapi.responses import Response, PlainTextResponse
from starlette.middleware.proxy_headers import ProxyHeadersMiddleware
import httpx

app = FastAPI()
app.add_middleware(ProxyHeadersMiddleware)

def run_streamlit():
    subprocess.run([
        "python", "-m", "streamlit", "run", "ticker_app_v13.py",
        "--server.port=8501",
        "--server.address=0.0.0.0"
    ])

threading.Thread(target=run_streamlit, daemon=True).start()

@app.get("/ads.txt")
async def ads():
    with open("ads.txt") as f:
        return PlainTextResponse(f.read(), media_type="text/plain")

@app.api_route("/{path:path}", methods=["GET", "POST"])
async def proxy(request: Request, path: str):
    url = f"http://localhost:8501/{path}"

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.request(
            request.method,
            url,
            content=await request.body(),
            headers=request.headers.raw,
            params=request.query_params
        )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type")
    )
