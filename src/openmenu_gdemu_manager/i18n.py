from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config.paths import LANGUAGES_DIR

log = logging.getLogger(__name__)

LANGUAGE_RE = re.compile(r"^[A-Za-z0-9_-]{2,16}$")
_REGISTRY: "TranslationRegistry | None" = None
_ACTIVE_LANGUAGE = "en"


@dataclass(frozen=True)
class LanguagePackage:
    code: str
    language_name: str
    native_name: str
    version: str
    author: str
    app_min_version: str
    strings: dict[str, str]
    internal: bool = False
    path: Path | None = None

    @property
    def label(self) -> str:
        if self.native_name and self.native_name != self.language_name:
            return f"{self.native_name} ({self.language_name})"
        return self.native_name or self.language_name or self.code


class TranslationRegistry:
    def __init__(self, languages_dir: Path = LANGUAGES_DIR):
        self.languages_dir = languages_dir
        self.languages: dict[str, LanguagePackage] = {}
        self.errors: list[str] = []
        self.refresh()

    def refresh(self) -> None:
        self.errors = []
        self.languages = {}
        for code in ("en", "es"):
            try:
                package = load_internal_language(code)
                self.languages[package.code] = package
            except Exception as exc:
                self.errors.append(f"{code}: {exc}")
                log.exception("Could not load built-in language %s", code)
        if "en" not in self.languages:
            self.languages["en"] = LanguagePackage(
                code="en",
                language_name="English",
                native_name="English",
                version="1.0.0",
                author="OpenMenu GDEMU Manager",
                app_min_version="0.1.0",
                strings={},
                internal=True,
            )
        for package in self._load_external_languages():
            self.languages[package.code] = package

    def _load_external_languages(self) -> list[LanguagePackage]:
        if not self.languages_dir.exists():
            return []
        packages: list[LanguagePackage] = []
        for path in sorted(self.languages_dir.glob("*.json")):
            try:
                package = load_language_file(path, internal=False)
                packages.append(package)
            except Exception as exc:
                self.errors.append(f"{path.name}: {exc}")
                log.warning("Ignoring invalid language file %s: %s", path, exc)
        return packages

    def normalize(self, code: str | None) -> str:
        value = str(code or "").strip()
        if value in self.languages:
            return value
        return "en"

    def translate(self, key: str, language: str | None = None, **kwargs: Any) -> str:
        lang = self.normalize(language or _ACTIVE_LANGUAGE)
        text = self.languages.get(lang, self.languages["en"]).strings.get(key)
        if text is None:
            text = self.languages["en"].strings.get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                log.warning("Could not format translation key=%s lang=%s", key, lang, exc_info=True)
        return text


def registry(refresh: bool = False, languages_dir: Path | None = None) -> TranslationRegistry:
    global _REGISTRY
    if refresh or _REGISTRY is None or (languages_dir and _REGISTRY.languages_dir != languages_dir):
        _REGISTRY = TranslationRegistry(languages_dir or LANGUAGES_DIR)
    return _REGISTRY


def refresh_languages(languages_dir: Path | None = None) -> TranslationRegistry:
    return registry(refresh=True, languages_dir=languages_dir)


def available_languages() -> list[LanguagePackage]:
    return list(registry().languages.values())


def set_language(code: str | None) -> str:
    global _ACTIVE_LANGUAGE
    _ACTIVE_LANGUAGE = registry().normalize(code)
    return _ACTIVE_LANGUAGE


def active_language() -> str:
    return _ACTIVE_LANGUAGE


def tr(key: str, **kwargs: Any) -> str:
    return registry().translate(key, **kwargs)


def translate_status(status: str) -> str:
    return tr(f"status.{status}") if status else tr("status.unknown")


def load_internal_language(code: str) -> LanguagePackage:
    resource = Path(__file__).resolve().parent / "resources" / "i18n" / f"{code}.json"
    data = json.loads(resource.read_text(encoding="utf-8"))
    return _package_from_data(data, internal=True, path=None)


def load_language_file(path: Path, internal: bool = False) -> LanguagePackage:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return _package_from_data(data, internal=internal, path=Path(path))


def _package_from_data(data: dict[str, Any], internal: bool, path: Path | None) -> LanguagePackage:
    code = str(data.get("language_code", "")).strip()
    if not LANGUAGE_RE.match(code):
        raise ValueError("invalid language_code")
    strings = data.get("strings", {})
    if not isinstance(strings, dict):
        raise ValueError("strings must be an object")
    return LanguagePackage(
        code=code,
        language_name=str(data.get("language_name", code)).strip() or code,
        native_name=str(data.get("native_name", data.get("language_name", code))).strip() or code,
        version=str(data.get("version", "1.0.0")),
        author=str(data.get("author", "")),
        app_min_version=str(data.get("app_min_version", "0.1.0")),
        strings={str(key): str(value) for key, value in strings.items()},
        internal=internal,
        path=path,
    )
