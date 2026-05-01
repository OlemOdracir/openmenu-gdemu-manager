import json
import urllib.request
from pathlib import Path
from typing import Any

from ...config.paths import CACHE_DIR


USER_AGENT = "openmenu-cover-manager"


def read_json_cache(cache_name: str, url: str) -> list | dict:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / cache_name
    if cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data: Any = json.loads(resp.read().decode("utf-8"))
    with cache_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)
    return data


def read_text_cache(cache_name: str, url: str) -> str:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / cache_name
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    cache_path.write_text(text, encoding="utf-8")
    return text


def is_image_path(path: Path | str) -> bool:
    return str(path).lower().endswith((".png", ".jpg", ".jpeg"))

