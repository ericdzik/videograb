import yt_dlp
import os
import re
from pathlib import Path

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Chemin local vers ffmpeg.exe (dans le dossier du projet)
FFMPEG_PATH = str(Path(__file__).parent / "ffmpeg.exe")


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name)


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
    fmt = format_id if format_id != "best" else "bestvideo+bestaudio/best"
    ydl_opts = {
        "format": fmt,
        "outtmpl": str(DOWNLOAD_DIR / "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "ffmpeg_location": FFMPEG_PATH,
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # handle merged mp4
        if not os.path.exists(filename):
            filename = filename.rsplit(".", 1)[0] + ".mp4"
        return {
            "title": info.get("title", "video"),
            "filename": os.path.basename(filename),
            "filepath": filename,
        }
