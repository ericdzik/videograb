from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
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

FILE_TTL = 600  # secondes avant suppression du fichier (10 min)


async def delete_after(filepath: str, delay: int = FILE_TTL):
    """Supprime le fichier après `delay` secondes."""
    await asyncio.sleep(delay)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception:
        pass


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
            # Supprime le fichier automatiquement après 10 min
            asyncio.create_task(delete_after(result["filepath"]))
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
async def serve_file(filename: str):
    """Sert le fichier vidéo — FileResponse gère les Range headers nativement."""
    filepath = DOWNLOAD_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    return FileResponse(
        path=str(filepath),
        media_type="video/mp4",
        filename=filename,
    )
