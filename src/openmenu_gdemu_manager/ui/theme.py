from __future__ import annotations

import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from .. import APP_NAME
from ..config.paths import UI_TEMPLATES_DIR


_ACTIVE_TEMPLATE = "basic_formal"
_TEMPLATE_REGISTRY: "ThemeRegistry | None" = None

SAFE_TEMPLATE_EXTENSIONS = {".json", ".png", ".jpg", ".jpeg", ".webp", ".mp3", ".ogg", ".wav"}
TEMPLATE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


BASE_PALETTE: dict[str, Any] = {
    "label": "Basico formal",
    "window_bg": "#f4f7fb",
    "surface": "#ffffff",
    "surface_alt": "#eef3f9",
    "surface_soft": "#f8fafc",
    "text": "#1f2a37",
    "muted": "#66758a",
    "border": "#d5dce6",
    "accent": "#2d6cdf",
    "accent_soft": "#e8f0ff",
    "accent_text": "#0c3d97",
    "success": "#1f8a4d",
    "success_soft": "#dff4e5",
    "warning": "#c17d10",
    "warning_soft": "#fff0cf",
    "danger": "#c0392b",
    "danger_soft": "#ffe2dd",
    "hover": "#edf4ff",
    "selected": "#dceaff",
    "table_header": "#e9eff7",
    "table_alt": "#f7faff",
    "shadow": "rgba(30, 41, 59, 0.10)",
    "background_overlay": "rgba(247, 244, 238, 0.78)",
}


INTERNAL_TEMPLATES: dict[str, dict[str, Any]] = {
    "basic_formal": {
        **BASE_PALETTE,
        "label": "Basico formal",
    },
    "arcade_clean": {
        **BASE_PALETTE,
        "label": "Arcade limpio",
        "window_bg": "#f7f4ee",
        "surface": "#fffdf8",
        "surface_alt": "#fff5e8",
        "surface_soft": "#fffaf1",
        "text": "#1f2933",
        "muted": "#5f6c75",
        "border": "#dfd4c6",
        "accent": "#ff7a18",
        "accent_soft": "#ffe3c8",
        "accent_text": "#8a3d00",
        "success": "#14746f",
        "success_soft": "#dff6f4",
        "warning": "#d17c00",
        "warning_soft": "#fff1cf",
        "danger": "#c44536",
        "danger_soft": "#ffe0dc",
        "hover": "#fff0db",
        "selected": "#ffe2c0",
        "table_header": "#ffe8cf",
        "table_alt": "#fffaf3",
        "shadow": "rgba(120, 53, 15, 0.14)",
        "background_overlay": "rgba(247, 244, 238, 0.76)",
    },
}


@dataclass(frozen=True)
class ThemePackage:
    id: str
    name: str
    version: str
    author: str
    license: str
    palette: dict[str, Any]
    root: Path | None = None
    background: dict[str, Any] | None = None
    music: dict[str, Any] | None = None
    internal: bool = False

    def background_path(self) -> Path | None:
        if self.root is None or not self.background:
            return None
        raw = str(self.background.get("file", "")).strip()
        if not raw:
            return None
        path = (self.root / raw).resolve()
        try:
            path.relative_to(self.root.resolve())
        except ValueError:
            return None
        return path if path.is_file() else None

    def music_path(self) -> Path | None:
        if self.root is None or not self.music:
            return None
        raw = str(self.music.get("file", "")).strip()
        if not raw:
            return None
        path = (self.root / raw).resolve()
        try:
            path.relative_to(self.root.resolve())
        except ValueError:
            return None
        return path if path.is_file() else None


class ThemeRegistry:
    def __init__(self, template_dir: Path = UI_TEMPLATES_DIR):
        self.template_dir = template_dir
        self.templates: dict[str, ThemePackage] = {}
        self.errors: list[str] = []
        self.refresh()

    def refresh(self) -> None:
        self.templates = _internal_templates()
        self.errors = []
        for package in self._load_external_templates():
            self.templates[package.id] = package

    def _load_external_templates(self) -> list[ThemePackage]:
        if not self.template_dir.exists():
            return []
        packages: list[ThemePackage] = []
        for folder in sorted(path for path in self.template_dir.iterdir() if path.is_dir()):
            manifest = folder / "theme.json"
            if not manifest.is_file():
                continue
            try:
                packages.append(load_theme_manifest(manifest))
            except Exception as exc:
                self.errors.append(f"{folder.name}: {exc}")
        return packages

    def normalize(self, template_id: str | None) -> str:
        value = str(template_id or "").strip()
        if value in self.templates:
            return value
        return "arcade_clean" if "arcade_clean" in self.templates else "basic_formal"

    def get(self, template_id: str | None) -> ThemePackage:
        return self.templates[self.normalize(template_id)]


def registry(refresh: bool = False, template_dir: Path | None = None) -> ThemeRegistry:
    global _TEMPLATE_REGISTRY
    if refresh or _TEMPLATE_REGISTRY is None or (template_dir and _TEMPLATE_REGISTRY.template_dir != template_dir):
        _TEMPLATE_REGISTRY = ThemeRegistry(template_dir or UI_TEMPLATES_DIR)
    return _TEMPLATE_REGISTRY


def refresh_templates(template_dir: Path | None = None) -> ThemeRegistry:
    return registry(refresh=True, template_dir=template_dir)


def available_templates() -> list[ThemePackage]:
    return list(registry().templates.values())


def normalized_template(name: str | None) -> str:
    return registry().normalize(name)


def template_package(name: str | None = None) -> ThemePackage:
    return registry().get(name or _ACTIVE_TEMPLATE)


def template_palette(name: str | None = None) -> dict[str, Any]:
    return template_package(name).palette


def template_label(name: str | None = None) -> str:
    return template_package(name).name


def set_active_template(name: str) -> str:
    global _ACTIVE_TEMPLATE
    _ACTIVE_TEMPLATE = normalized_template(name)
    return _ACTIVE_TEMPLATE


def active_template() -> str:
    return _ACTIVE_TEMPLATE


def apply_template(app, template_name: str) -> str:
    selected = set_active_template(template_name)
    app.setStyleSheet(build_stylesheet(selected))
    return selected


def load_theme_manifest(manifest_path: Path) -> ThemePackage:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent.resolve()
    for field in ("id", "name", "version", "author", "license", "palette"):
        if field not in data:
            raise ValueError(f"theme.json incompleto: falta {field}")
    if not isinstance(data.get("palette"), dict):
        raise ValueError("theme.json invalido: palette debe ser objeto")
    template_id = str(data.get("id", "")).strip()
    if not TEMPLATE_ID_RE.match(template_id):
        raise ValueError("id de template invalido")
    name = str(data.get("name", template_id)).strip() or template_id
    palette = _merged_palette(name, data.get("palette", {}))
    background = _validated_asset_block(root, data.get("background"), {"image"})
    music = _validated_asset_block(root, data.get("music"), {"audio"})
    return ThemePackage(
        id=template_id,
        name=name,
        version=str(data.get("version", "1.0.0")),
        author=str(data.get("author", "")),
        license=str(data.get("license", "")),
        palette=palette,
        root=root,
        background=background,
        music=music,
        internal=False,
    )


def install_template_package(source: str | Path, template_dir: Path = UI_TEMPLATES_DIR) -> ThemePackage:
    template_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="openmenu_template_") as tmp_raw:
        tmp_dir = Path(tmp_raw)
        zip_path = _resolve_zip_source(source, tmp_dir)
        _validate_zip_members(zip_path)
        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(extract_dir)
        manifest = _find_manifest(extract_dir)
        package = load_theme_manifest(manifest)
        destination = (template_dir / package.id).resolve()
        _ensure_child(destination, template_dir.resolve())
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(manifest.parent, destination)
    refresh_templates(template_dir)
    return registry(template_dir=template_dir).get(package.id)


def build_stylesheet(template_name: str) -> str:
    c = template_palette(template_name)
    combo_arrow = files("openmenu_gdemu_manager.resources.icons").joinpath("chevron_down.svg")
    combo_arrow_url = str(combo_arrow).replace("\\", "/")
    return f"""
QMainWindow, QDialog, QWidget {{
    background: {c['window_bg']};
    color: {c['text']};
    font-family: "Segoe UI", "Trebuchet MS", sans-serif;
    font-size: 10.5pt;
}}
QWidget#MainRoot {{
    background: transparent;
}}
QMenuBar {{
    background: {c['surface']};
    border-bottom: 1px solid {c['border']};
}}
QMenuBar::item {{
    padding: 6px 12px;
    margin: 3px 4px;
    border-radius: 8px;
}}
QMenuBar::item:selected {{
    background: {c['hover']};
}}
QMenu {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 14px;
    border-radius: 8px;
}}
QMenu::item:selected {{
    background: {c['hover']};
}}
QMenu::item:checked {{
    background: {c['accent_soft']};
    color: {c['accent_text']};
}}
QLineEdit, QComboBox {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    padding: 8px 12px;
    selection-background-color: {c['selected']};
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {c['accent']};
}}
QComboBox {{
    padding-right: 34px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    border-left: 1px solid {c['border']};
    border-top-right-radius: 12px;
    border-bottom-right-radius: 12px;
    background: {c['surface_soft']};
}}
QComboBox::drop-down:hover {{
    background: {c['hover']};
}}
QComboBox::down-arrow {{
    image: url("{combo_arrow_url}");
    width: 16px;
    height: 16px;
}}
QComboBox QAbstractItemView {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 6px;
    outline: none;
    selection-background-color: {c['selected']};
    selection-color: {c['text']};
}}
QPushButton {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    padding: 7px 10px;
    color: {c['text']};
}}
QPushButton:hover {{
    background: {c['hover']};
}}
QPushButton:pressed {{
    background: {c['selected']};
}}
QPushButton:disabled {{
    color: {c['muted']};
    background: {c['surface_alt']};
    border-color: {c['border']};
}}
QPushButton[variant="accent"] {{
    background: {c['accent_soft']};
    color: {c['accent_text']};
    border-color: {c['accent']};
    font-weight: 600;
}}
QPushButton[variant="success"] {{
    background: {c['success_soft']};
    color: {c['success']};
    border-color: {c['success']};
    font-weight: 600;
}}
QPushButton[attention="true"] {{
    background: {c['success_soft']};
    color: {c['success']};
    border: 2px solid {c['success']};
    font-weight: 800;
    padding: 6px 12px;
}}
QPushButton[attention="true"][pulse="true"] {{
    background: {c['success_soft']};
    color: {c['success']};
    border: 2px solid #29f3a7;
}}
QPushButton[variant="warning"] {{
    background: {c['warning_soft']};
    color: {c['warning']};
    border-color: {c['warning']};
    font-weight: 600;
}}
QPushButton[variant="danger"] {{
    background: {c['danger_soft']};
    color: {c['danger']};
    border-color: {c['danger']};
    font-weight: 600;
}}
QPushButton[variant="accent"]:disabled,
QPushButton[variant="success"]:disabled,
QPushButton[variant="warning"]:disabled,
QPushButton[variant="danger"]:disabled,
QPushButton[variant="toggle"]:disabled,
QPushButton[attention="true"]:disabled {{
    background: {c['surface_alt']};
    color: {c['muted']};
    border-color: {c['border']};
    font-weight: 500;
}}
QPushButton[variant="toggle"][checked="true"],
QPushButton[variant="toggle"]:checked {{
    background: {c['accent_soft']};
    color: {c['accent_text']};
    border-color: {c['accent']};
    font-weight: 600;
}}
QPushButton[iconOnly="true"] {{
    min-width: 40px;
    max-width: 40px;
    min-height: 40px;
    max-height: 40px;
    padding: 0px;
}}
QLabel#SectionTitle {{
    font-size: 12pt;
    font-weight: 700;
    color: {c['text']};
}}
QLabel#MutedLabel {{
    color: {c['muted']};
}}
QLabel#AppLogo {{
    background: transparent;
    border: none;
}}
QLabel#SecurityIcon {{
    background: transparent;
    border: none;
}}
QLabel#Chip, QLabel#ChipAccent, QLabel#ChipSuccess, QLabel#ChipWarning {{
    border-radius: 12px;
    padding: 5px 10px;
    font-weight: 600;
}}
QLabel#Chip {{
    background: {c['surface_alt']};
    color: {c['text']};
    border: 1px solid {c['border']};
}}
QLabel#ChipAccent {{
    background: {c['accent_soft']};
    color: {c['accent_text']};
    border: 1px solid {c['accent']};
}}
QLabel#ChipSuccess {{
    background: {c['success_soft']};
    color: {c['success']};
    border: 1px solid {c['success']};
}}
QLabel#ChipWarning {{
    background: {c['warning_soft']};
    color: {c['warning']};
    border: 1px solid {c['warning']};
}}
QWidget#TopBar, QWidget#FilterBar, QWidget#DialogToolbar, QWidget#BusyPanel {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 16px;
}}
QWidget#StatusCard {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 16px;
}}
QWidget#StatusCardDanger {{
    background: {c['danger_soft']};
    border: 1px solid {c['danger']};
    border-radius: 16px;
}}
QWidget#StatusCardWarning {{
    background: {c['warning_soft']};
    border: 1px solid {c['warning']};
    border-radius: 16px;
}}
QWidget#StatusCardSuccess {{
    background: {c['success_soft']};
    border: 1px solid {c['success']};
    border-radius: 16px;
}}
QWidget#WizardHero {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['surface']}, stop:1 {c['accent_soft']});
    border: 1px solid {c['border']};
    border-radius: 18px;
}}
QLabel#WizardTitle {{
    font-size: 18pt;
    font-weight: 800;
    background: transparent;
}}
QLabel#WizardSubtitle {{
    font-size: 11pt;
    color: {c['muted']};
    background: transparent;
}}
QWidget#RouteCard, QWidget#DiagnosticTile {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 18px;
}}
QWidget#SecurityCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['warning_soft']}, stop:1 {c['surface']});
    border: 1px solid {c['warning']};
    border-radius: 18px;
}}
QWidget#SecurityCardDanger {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['danger_soft']}, stop:1 {c['surface']});
    border: 1px solid {c['danger']};
    border-radius: 18px;
}}
QWidget#SecurityCardSuccess {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['success_soft']}, stop:1 {c['surface']});
    border: 1px solid {c['success']};
    border-radius: 18px;
}}
QWidget#DiagnosticTileSuccess {{
    background: {c['success_soft']};
    border: 1px solid {c['success']};
    border-radius: 16px;
}}
QWidget#DiagnosticTileWarning {{
    background: {c['warning_soft']};
    border: 1px solid {c['warning']};
    border-radius: 16px;
}}
QWidget#DiagnosticTileDanger {{
    background: {c['danger_soft']};
    border: 1px solid {c['danger']};
    border-radius: 16px;
}}
QLabel#TileTitle {{
    font-size: 10.5pt;
    font-weight: 800;
    background: transparent;
}}
QLabel#TileValue {{
    font-size: 10pt;
    background: transparent;
}}
QLabel#CountBadge {{
    background: {c['muted']};
    color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    font-size: 9pt;
    font-weight: 800;
}}
QLabel#StatusTitle {{
    font-size: 12.5pt;
    font-weight: 700;
    background: transparent;
}}
QLabel#StatusMessage {{
    font-size: 10.5pt;
    background: transparent;
}}
QLabel#CurrentCover, QLabel#CandidatePreview {{
    background: {c['surface_soft']};
    border: 1px solid {c['border']};
    border-radius: 14px;
}}
QFrame#CandidateCard {{
    border: 1px solid {c['border']};
    border-radius: 14px;
    background: {c['surface_alt']};
}}
QLabel#QualityBadgeSuccess {{
    background: {c['success']};
    color: {c['surface']};
    border-radius: 10px;
    padding: 4px 8px;
    font-size: 9pt;
    font-weight: 700;
}}
QLabel#QualityBadgeWarning {{
    background: {c['warning']};
    color: {c['surface']};
    border-radius: 10px;
    padding: 4px 8px;
    font-size: 9pt;
    font-weight: 700;
}}
QLabel#QualityBadgeDanger {{
    background: {c['danger']};
    color: {c['surface']};
    border-radius: 10px;
    padding: 4px 8px;
    font-size: 9pt;
    font-weight: 700;
}}
QTableView, QTableWidget {{
    background: {c['surface']};
    alternate-background-color: {c['table_alt']};
    border: 1px solid {c['border']};
    border-radius: 16px;
    gridline-color: {c['border']};
    selection-background-color: {c['selected']};
    selection-color: {c['text']};
}}
QHeaderView::section {{
    background: {c['table_header']};
    color: {c['text']};
    padding: 10px 8px;
    border: none;
    border-bottom: 1px solid {c['border']};
    font-weight: 700;
}}
QTableView::item {{
    padding: 6px;
}}
QTableView::item:hover {{
    background: {c['hover']};
}}
QGroupBox {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 16px;
    margin-top: 10px;
    padding-top: 14px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 2px 6px;
}}
QScrollArea {{
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 8px 2px 8px 2px;
}}
QScrollBar::handle:vertical {{
    background: {c['border']};
    border-radius: 5px;
    min-height: 42px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['muted']};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
    background: transparent;
    border: none;
}}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 2px 8px 2px 8px;
}}
QScrollBar::handle:horizontal {{
    background: {c['border']};
    border-radius: 5px;
    min-width: 42px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {c['muted']};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: transparent;
    border: none;
}}
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    background: transparent;
}}
QProgressBar {{
    background: {c['surface_alt']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    min-height: 16px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {c['accent']};
    border-radius: 10px;
}}
QToolTip {{
    background: {c['surface']};
    color: {c['text']};
    border: 1px solid {c['border']};
    padding: 6px 8px;
}}
QWidget#BusyOverlay {{
    background: rgba(15, 23, 42, 0.14);
}}
QWidget#SpinnerLabel {{
    background: transparent;
}}
QLabel#BusyTitle {{
    font-size: 12pt;
    font-weight: 700;
}}
QLabel#BusyDetail {{
    color: {c['muted']};
}}
"""


def _internal_templates() -> dict[str, ThemePackage]:
    result: dict[str, ThemePackage] = {}
    for template_id, palette in INTERNAL_TEMPLATES.items():
        result[template_id] = ThemePackage(
            id=template_id,
            name=str(palette["label"]),
            version="1.0.0",
            author=APP_NAME,
            license="MIT",
            palette=dict(palette),
            internal=True,
        )
    return result


def _merged_palette(label: str, palette: Any) -> dict[str, Any]:
    merged = dict(BASE_PALETTE)
    merged["label"] = label
    if isinstance(palette, dict):
        for key, value in palette.items():
            if key in merged:
                merged[key] = str(value)
    return merged


def _validated_asset_block(root: Path, block: Any, expected: set[str]) -> dict[str, Any] | None:
    if not isinstance(block, dict):
        return None
    raw = str(block.get("file", "")).strip()
    if not raw:
        return None
    asset = (root / raw).resolve()
    _ensure_child(asset, root)
    if not asset.is_file():
        raise ValueError(f"asset no encontrado: {raw}")
    suffix = asset.suffix.lower()
    if "image" in expected and suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError(f"imagen no permitida: {raw}")
    if "audio" in expected and suffix not in {".mp3", ".ogg", ".wav"}:
        raise ValueError(f"audio no permitido: {raw}")
    return dict(block)


def _resolve_zip_source(source: str | Path, tmp_dir: Path) -> Path:
    value = str(source)
    if value.lower().startswith(("http://", "https://")):
        target = tmp_dir / "template.zip"
        with urllib.request.urlopen(value, timeout=30) as response:
            target.write_bytes(response.read())
        return target
    path = Path(value).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"No existe el paquete: {path}")
    return path


def _validate_zip_members(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as archive:
        for info in archive.infolist():
            raw = info.filename.replace("\\", "/")
            parts = Path(raw).parts
            if info.file_size > 80 * 1024 * 1024:
                raise ValueError(f"archivo demasiado grande: {raw}")
            if Path(raw).is_absolute() or ".." in parts:
                raise ValueError(f"ruta insegura en template: {raw}")
            if raw.endswith("/"):
                continue
            suffix = Path(raw).suffix.lower()
            if suffix not in SAFE_TEMPLATE_EXTENSIONS:
                raise ValueError(f"extension no permitida en template: {raw}")


def _find_manifest(root: Path) -> Path:
    manifests = [path for path in root.rglob("theme.json") if path.is_file()]
    if len(manifests) != 1:
        raise ValueError("el paquete debe contener exactamente un theme.json")
    return manifests[0]


def _ensure_child(path: Path, parent: Path) -> None:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError as exc:
        raise ValueError(f"ruta fuera del template: {path}") from exc
