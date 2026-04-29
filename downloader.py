import yt_dlp
import os
import re
import uuid
from pathlib import Path

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Utilise ffmpeg local sur Windows, système sur Linux (Railway)
_local_ffmpeg = Path(__file__).parent / "ffmpeg.exe"
FFMPEG_PATH = str(_local_ffmpeg) if _local_ffmpeg.exists() else "ffmpeg"


def get_video_info(url: str) -> dict:
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = []
        seen = set()
        for f in info.get("formats", []):
            label = None
            if f.get("vcodec") != "none" and f.get("height"):
                label = f"{f['height']}p"
            elif f.get("acodec") != "none" and f.get("vcodec") == "none":
                label = "audio only"
            if label and label not in seen:
                seen.add(label)
                formats.append({
                    "format_id": f["format_id"],
                    "label": label,
                    "ext": f.get("ext", "mp4"),
                })
        return {
            "title": info.get("title", "video"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "platform": info.get("extractor_key", "Unknown"),
            "formats": formats,
        }


def download_video(url: str, format_id: str = "best") -> dict:
    # Utilise un nom de fichier unique (UUID) pour éviter tout problème
    # de caractères spéciaux, espaces, emojis dans le titre
    file_id = str(uuid.uuid4())
    output_path = str(DOWNLOAD_DIR / f"{file_id}.mp4")

    fmt = format_id if format_id != "best" else "bestvideo+bestaudio/best"

    ydl_opts = {
        "format": fmt,
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "ffmpeg_location": FFMPEG_PATH,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "video")

    # Le fichier est toujours à output_path car on a forcé le nom
    if not os.path.exists(output_path):
        raise FileNotFoundError(f"Le fichier téléchargé est introuvable : {output_path}")

    return {
        "title": title,
        "filename": f"{file_id}.mp4",
        "filepath": output_path,
    }
