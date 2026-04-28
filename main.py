from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from downloader import get_video_info, download_video, DOWNLOAD_DIR

app = FastAPI(title="Video Downloader")
app.mount("/static", StaticFiles(directory="static"), name="static")


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
        info = get_video_info(req.url)
        return {"success": True, "data": info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/download")
async def download(req: DownloadRequest):
    try:
        result = download_video(req.url, req.format_id)
        return {"success": True, "filename": result["filename"], "title": result["title"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/file/{filename}")
async def serve_file(filename: str):
    filepath = DOWNLOAD_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
