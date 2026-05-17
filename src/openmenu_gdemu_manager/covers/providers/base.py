import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from ...config.paths import CACHE_DIR

try:
    import certifi
except ImportError:  # pragma: no cover - dependency is declared for packaged builds
    certifi = None


USER_AGENT = "openmenu-cover-manager"
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_TEXT_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
RETRY_COUNT = 2
RATE_LIMIT_SECONDS = 0.12

_last_request_by_host: dict[str, float] = {}


class RemoteContentError(RuntimeError):
    """Raised when remote content does not pass basic safety checks."""


def read_remote_bytes(
    url: str,
    *,
    timeout: int = 30,
    max_bytes: int,
    accept: str = "*/*",
    allowed_content_types: tuple[str, ...] = (),
    retries: int = RETRY_COUNT,
) -> bytes:
    _validate_https_url(url)
    headers = {"User-Agent": USER_AGENT, "Accept": accept}
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            _rate_limit(url)
            req = urllib.request.Request(url, headers=headers)
            with _urlopen(req, timeout=timeout) as resp:
                final_url = getattr(resp, "url", "") or getattr(resp, "geturl", lambda: "")()
                if final_url:
                    _validate_https_url(str(final_url))
                _validate_content_type(resp, allowed_content_types)
                return _read_limited(resp, max_bytes)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= retries:
                raise
            time.sleep(0.4 * (attempt + 1))
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt >= retries:
                raise
            time.sleep(0.4 * (attempt + 1))
    raise RemoteContentError(f"No se pudo descargar contenido remoto: {last_error}")


def _urlopen(request: urllib.request.Request, timeout: int):
    context = _default_ssl_context()
    if context is None:
        return urllib.request.urlopen(request, timeout=timeout)
    try:
        return urllib.request.urlopen(request, timeout=timeout, context=context)
    except TypeError as exc:
        if "context" not in str(exc):
            raise
        return urllib.request.urlopen(request, timeout=timeout)


def _default_ssl_context() -> ssl.SSLContext | None:
    if certifi is None:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def read_json_url(url: str, timeout: int = 30) -> list | dict:
    data = read_remote_bytes(
        url,
        timeout=timeout,
        max_bytes=MAX_JSON_BYTES,
        accept="application/json",
        allowed_content_types=("application/json", "application/vnd.github+json", "text/json", "text/plain"),
    )
    return json.loads(data.decode("utf-8"))


def read_text_url(url: str, timeout: int = 30) -> str:
    data = read_remote_bytes(
        url,
        timeout=timeout,
        max_bytes=MAX_TEXT_BYTES,
        accept="text/plain,*/*",
        allowed_content_types=("text/plain", "text/csv", "application/octet-stream", "application/vnd.github.raw"),
    )
    return data.decode("utf-8", errors="replace")


def read_image_url(url: str, timeout: int = 30) -> bytes:
    return read_remote_bytes(
        url,
        timeout=timeout,
        max_bytes=MAX_IMAGE_BYTES,
        accept="image/png,image/jpeg,image/webp",
        allowed_content_types=("image/png", "image/jpeg", "image/jpg", "image/webp", "application/octet-stream"),
    )


def read_json_cache(cache_name: str, url: str) -> list | dict:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / cache_name
    if cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    data: Any = read_json_url(url, timeout=30)
    with cache_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)
    return data


def read_text_cache(cache_name: str, url: str) -> str:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / cache_name
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="replace")
    text = read_text_url(url, timeout=30)
    cache_path.write_text(text, encoding="utf-8")
    return text


def is_image_path(path: Path | str) -> bool:
    return str(path).lower().endswith((".png", ".jpg", ".jpeg", ".webp"))


def _validate_https_url(url: str) -> None:
    parsed = urllib.parse.urlparse(str(url))
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise RemoteContentError(f"URL remota no segura: {url}")


def _rate_limit(url: str) -> None:
    parsed = urllib.parse.urlparse(str(url))
    host = parsed.netloc.lower()
    if not host:
        return
    now = time.monotonic()
    last = _last_request_by_host.get(host, 0.0)
    delay = RATE_LIMIT_SECONDS - (now - last)
    if delay > 0:
        time.sleep(delay)
    _last_request_by_host[host] = time.monotonic()


def _validate_content_type(resp, allowed_content_types: tuple[str, ...]) -> None:
    if not allowed_content_types:
        return
    content_type = ""
    try:
        content_type = str(resp.headers.get("Content-Type", ""))
    except Exception:
        try:
            content_type = str(resp.getheader("Content-Type", ""))
        except Exception:
            content_type = ""
    if not content_type:
        return
    normalized = content_type.split(";", 1)[0].strip().lower()
    allowed = {item.lower() for item in allowed_content_types}
    if normalized not in allowed:
        raise RemoteContentError(f"Tipo de contenido remoto no permitido: {content_type}")


def _read_limited(resp, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        try:
            chunk = resp.read(64 * 1024)
        except TypeError:
            chunk = resp.read()
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise RemoteContentError(f"Contenido remoto excede el limite de {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)
