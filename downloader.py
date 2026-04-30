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

# Cookies YouTube — fichier local ou variable d'environnement (Railway)
_cookies_file = Path(__file__).parent / "cookies.txt"
if _cookies_file.exists():
    COOKIES_PATH = str(_cookies_file)
elif os.environ.get("YOUTUBE_COOKIES"):
    # Sur Railway : colle le contenu du cookies.txt dans la variable YOUTUBE_COOKIES
    COOKIES_PATH = str(DOWNLOAD_DIR / "_cookies.txt")
    with open(COOKIES_PATH, "w") as f:
        f.write(os.environ["YOUTUBE_COOKIES"])
else:
    COOKIES_PATH = None


def get_video_info(url: str) -> dict:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extractor_args": {"youtube": {"player_client": ["mweb", "web"]}},
    }
    if COOKIES_PATH:
        ydl_opts["cookiefile"] = COOKIES_PATH
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = []
        seen = set()
        for f in info.get("formats", []):
            # Garde uniquement les formats qui ont vidéo ET audio ensemble
            # (pas les formats séparés qui nécessitent un merge)
            has_video = f.get("vcodec") != "none" and f.get("height")
            has_audio = f.get("acodec") != "none"
            if has_video and has_audio:
                label = f"{f['height']}p"
                if label not in seen:
                    seen.add(label)
                    formats.append({
                        "format_id": f["format_id"],
                        "label": label,
                        "ext": f.get("ext", "mp4"),
                    })

        # Si aucun format combiné trouvé (ex: YouTube), on propose des options génériques
        if not formats:
            formats = [
                {"format_id": "best[ext=mp4]", "label": "Meilleure qualité MP4", "ext": "mp4"},
                {"format_id": "worst[ext=mp4]", "label": "Qualité réduite MP4", "ext": "mp4"},
            ]

        return {
            "title": info.get("title", "video"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "platform": info.get("extractor_key", "Unknown"),
            "formats": formats,
        }


def download_video(url: str, format_id: str = "best") -> dict:
    file_id = str(uuid.uuid4())
    output_path = str(DOWNLOAD_DIR / f"{file_id}.mp4")

    # Stratégie de format robuste :
    # - Si format_id spécifique → on essaie, avec fallback sur best mp4
    # - Si "best" → on prend le meilleur format avec vidéo+audio déjà combinés
    if format_id == "best":
        fmt = "best[ext=mp4]/best"
    elif format_id in ("best[ext=mp4]", "worst[ext=mp4]"):
        fmt = format_id
    else:
        # Format spécifique sélectionné par l'utilisateur, fallback si indispo
        fmt = f"{format_id}/best[ext=mp4]/best"

    ydl_opts = {
        "format": fmt,
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "ffmpeg_location": FFMPEG_PATH,
        "extractor_args": {"youtube": {"player_client": ["mweb", "web"]}},
    }
    if COOKIES_PATH:
        ydl_opts["cookiefile"] = COOKIES_PATH

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "video")

    if not os.path.exists(output_path):
        raise FileNotFoundError(f"Le fichier téléchargé est introuvable : {output_path}")

    return {
        "title": title,
        "filename": f"{file_id}.mp4",
        "filepath": output_path,
    }
