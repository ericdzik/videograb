from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import uuid
import asyncio
from pathlib import Path
from downloader import get_video_info, download_video, DOWNLOAD_DIR

app = FastAPI(title="Video Downloader")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Stockage en mémoire des jobs { job_id: { status, filename, title, error } }
jobs: dict = {}


class URLRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format_id: str = "best"


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/info")
async def video_info(req: URLRequest):
    try:
        info = await asyncio.to_thread(get_video_info, req.url)
        return {"success": True, "data": info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/download/start")
async def download_start(req: DownloadRequest):
    """Lance le téléchargement en arrière-plan et retourne un job_id."""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "filename": None, "title": None, "error": None}

    async def run():
        try:
            jobs[job_id]["status"] = "downloading"
            result = await asyncio.to_thread(download_video, req.url, req.format_id)
            jobs[job_id]["status"] = "done"
            jobs[job_id]["filename"] = result["filename"]
            jobs[job_id]["title"] = result["title"]
        except Exception as e:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = str(e)

    asyncio.create_task(run())
    return {"job_id": job_id}


@app.get("/api/download/status/{job_id}")
async def download_status(job_id: str):
    """Polling : retourne l'état du job."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job introuvable")
    return job


@app.get("/api/file/{filename}")
async def serve_file(filename: str, request: Request):
    """Sert le fichier avec support Range (requis pour iOS Safari)."""
    filepath = DOWNLOAD_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    file_size = filepath.stat().st_size
    range_header = request.headers.get("range")

    def iter_file(start: int, end: int, chunk: int = 1024 * 256):
        with open(filepath, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                data = f.read(min(chunk, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    if range_header:
        # Parse Range: bytes=start-end
        range_val = range_header.replace("bytes=", "")
        parts = range_val.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        content_length = end - start + 1

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        return StreamingResponse(
            iter_file(start, end),
            status_code=206,
            headers=headers,
            media_type="video/mp4",
        )

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return StreamingResponse(
        iter_file(0, file_size - 1),
        status_code=200,
        headers=headers,
        media_type="video/mp4",
    )
