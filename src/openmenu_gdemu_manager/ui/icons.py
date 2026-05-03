from __future__ import annotations

from functools import lru_cache
from importlib.resources import files

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from .theme import template_palette


ICON_ALIASES = {
    "bulk_search": "search",
    "correct": "select",
}

TABLER_ACTION_ICONS = {
    "add": "plus",
    "browse": "folder-open",
    "bulk_mode": "list",
    "bulk_search": "search",
    "cache": "database",
    "candidate_pick": "photo",
    "close": "x",
    "correct": "check",
    "discard": "trash",
    "inbox": "folder",
    "local_file": "file",
    "log": "file",
    "music": "world",
    "rename": "device-floppy",
    "report": "file",
    "save": "device-floppy",
    "scan": "refresh",
    "search": "search",
    "select": "circle-check",
    "source": "world",
    "warning": "alert-triangle",
    "web": "world",
    "install_template": "folder-open",
    "templates_folder": "folder-cog",
    "volume": "settings",
}


def action_qicon(action_name: str, variant: str = "default", size: int = 24) -> QIcon:
    palette = template_palette()
    color = _variant_color(palette, variant)
    tabler_icon = TABLER_ACTION_ICONS.get(action_name)
    if tabler_icon:
        return vendor_svg_icon("tabler", tabler_icon, color, size)
    soft = _variant_soft_color(palette, variant)
    return svg_icon(action_name, color, soft, size)


def vendor_qicon(pack: str, icon_name: str, variant: str = "default", size: int = 24) -> QIcon:
    palette = template_palette()
    color = _variant_color(palette, variant)
    return vendor_svg_icon(pack, icon_name, color, size)


def status_qicon(status: str, size: int = 24) -> QIcon:
    palette = template_palette()
    color, glyph = _status_icon_spec(status, palette)
    return badge_icon(glyph, color, size)


@lru_cache(maxsize=1)
def app_qicon() -> QIcon:
    path = files("openmenu_gdemu_manager.resources.app").joinpath("app_icon.png")
    return QIcon(str(path))


@lru_cache(maxsize=64)
def app_logo_pixmap(size: int) -> QPixmap:
    path = files("openmenu_gdemu_manager.resources.app").joinpath("app_icon.png")
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return QPixmap(QSize(size, size))
    return pixmap.scaled(QSize(size, size), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


@lru_cache(maxsize=16)
def sd_card_qicon(size: int = 24) -> QIcon:
    path = files("openmenu_gdemu_manager.resources.illustrations").joinpath("sd_card_dark_128.png")
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return action_qicon("browse", "default", size)
    pixmap = pixmap.scaled(QSize(size, size), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return _stable_icon(pixmap)


@lru_cache(maxsize=64)
def illustration_pixmap(name: str, size: int) -> QPixmap:
    path = files("openmenu_gdemu_manager.resources.illustrations").joinpath(f"{name}_{size}.png")
    if not path.is_file():
        path = files("openmenu_gdemu_manager.resources.illustrations").joinpath(f"{name}_512.png")
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return QPixmap(QSize(size, size))
    return pixmap.scaled(QSize(size, size), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


@lru_cache(maxsize=256)
def svg_icon(action_name: str, color: str, soft: str, size: int = 24) -> QIcon:
    icon_name = ICON_ALIASES.get(action_name, action_name)
    svg = _read_svg(icon_name)
    svg = svg.replace("__FG__", color).replace("__SOFT__", soft)
    renderer = QSvgRenderer(svg.encode("utf-8"))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return _stable_icon(pixmap)


@lru_cache(maxsize=256)
def vendor_svg_icon(pack: str, icon_name: str, color: str, size: int = 24) -> QIcon:
    svg = _read_vendor_svg(pack, icon_name)
    svg = svg.replace("currentColor", color)
    renderer = QSvgRenderer(svg.encode("utf-8"))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return _stable_icon(pixmap)


@lru_cache(maxsize=128)
def badge_icon(glyph: str, color: str, size: int = 24) -> QIcon:
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    margin = max(1, size // 12)
    painter.drawEllipse(margin, margin, size - margin * 2, size - margin * 2)
    font = QFont("Segoe UI", max(8, int(size * 0.48)))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#fffdf8"))
    painter.drawText(pixmap.rect(), int(Qt.AlignmentFlag.AlignCenter), glyph)
    painter.end()
    return _stable_icon(pixmap)


def _stable_icon(pixmap: QPixmap) -> QIcon:
    icon = QIcon()
    disabled = _disabled_pixmap(pixmap)
    icon.addPixmap(pixmap, QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(disabled, QIcon.Mode.Disabled, QIcon.State.Off)
    icon.addPixmap(pixmap, QIcon.Mode.Active, QIcon.State.Off)
    return icon


def _disabled_pixmap(pixmap: QPixmap) -> QPixmap:
    image = pixmap.toImage().convertToFormat(pixmap.toImage().Format.Format_ARGB32)
    muted = QColor(template_palette()["muted"])
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            alpha = color.alpha()
            if alpha == 0:
                continue
            color.setRed(muted.red())
            color.setGreen(muted.green())
            color.setBlue(muted.blue())
            color.setAlpha(int(alpha * 0.45))
            image.setPixelColor(x, y, color)
    return QPixmap.fromImage(image)


def _read_svg(icon_name: str) -> str:
    path = files("openmenu_gdemu_manager.resources.icons").joinpath(f"{icon_name}.svg")
    if not path.is_file():
        path = files("openmenu_gdemu_manager.resources.icons").joinpath("source.svg")
    return path.read_text(encoding="utf-8")


def _read_vendor_svg(pack: str, icon_name: str) -> str:
    path = files(f"openmenu_gdemu_manager.resources.vendor.{pack}").joinpath(f"{icon_name}.svg")
    if not path.is_file():
        path = files(f"openmenu_gdemu_manager.resources.vendor.{pack}").joinpath("alert-triangle.svg")
    return path.read_text(encoding="utf-8")


def _variant_color(palette: dict, variant: str) -> str:
    if variant == "success":
        return palette["success"]
    if variant == "warning":
        return palette["warning"]
    if variant == "danger":
        return palette["danger"]
    if variant in {"accent", "toggle"}:
        return palette["accent"]
    return palette["text"]


def _variant_soft_color(palette: dict, variant: str) -> str:
    if variant == "success":
        return palette["success_soft"]
    if variant == "warning":
        return palette["warning_soft"]
    if variant == "danger":
        return palette["danger_soft"]
    if variant in {"accent", "toggle"}:
        return palette["accent_soft"]
    return palette["surface_alt"]


def _status_icon_spec(status: str, palette: dict) -> tuple[str, str]:
    normalized = str(status or "").lower()
    if normalized in {"correcta", "guardado"}:
        return palette["success"], "v"
    if normalized in {"seleccionada", "propuesta_auto"}:
        return palette["accent"], "*"
    if normalized in {"revision", "dudosa", "pendiente_guardar"}:
        return palette["warning"], "!"
    if normalized in {"faltante", "sin_caratula", "pendiente_eliminar", "error"}:
        return palette["danger"], "x"
    if normalized in {"omitida"}:
        return palette["muted"], "-"
    return palette["muted"], "?"
