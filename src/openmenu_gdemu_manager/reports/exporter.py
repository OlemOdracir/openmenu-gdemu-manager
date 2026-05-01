import json
from dataclasses import asdict
from pathlib import Path

from ..core.models import GameItem
from ..config.paths import REPORT_JSON, REPORT_TSV


def export_reports(games: list[GameItem], tsv_path: Path = REPORT_TSV, json_path: Path = REPORT_JSON) -> tuple[Path, Path]:
    rows = [_row(game) for game in games]
    _write_tsv(rows, tsv_path)
    _write_json(rows, json_path)
    return tsv_path, json_path


def export_report(games: list[GameItem], path: Path) -> Path:
    rows = [_row(game) for game in games]
    suffix = path.suffix.lower()
    if suffix == ".json":
        _write_json(rows, path)
        return path
    if suffix in {"", ".tsv"}:
        if suffix == "":
            path = path.with_suffix(".tsv")
        _write_tsv(rows, path)
        return path
    raise ValueError(f"Formato de reporte no soportado: {path.suffix}")


def _headers() -> list[str]:
    return [
        "slot",
        "nombre",
        "product_id",
        "region",
        "estado",
        "imagen_actual",
        "imagen_seleccionada",
        "imagen_original",
        "imagen_preview",
        "fuente",
        "score",
        "calidad",
        "quality_score",
        "width",
        "height",
        "normalization_mode",
        "source_path",
        "is_new",
        "pending_add",
        "pending_delete",
        "has_placeholder_cover",
        "save_status",
    ]


def _write_tsv(rows: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        headers = _headers()
        handle.write("\t".join(headers) + "\n")
        for row in rows:
            handle.write("\t".join(str(row[h]) for h in headers) + "\n")


def _write_json(rows: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)


def _row(game: GameItem) -> dict:
    return {
        "slot": f"{game.slot:03d}",
        "nombre": game.name,
        "product_id": game.product_id,
        "region": game.region,
        "estado": game.status,
        "imagen_actual": str(game.current_cover or ""),
        "imagen_seleccionada": game.selected_image,
        "imagen_original": game.original_image,
        "imagen_preview": game.preview_image,
        "fuente": game.selected_source,
        "score": game.selected_score,
        "calidad": game.quality_label,
        "quality_score": game.quality_score,
        "width": game.image_width,
        "height": game.image_height,
        "normalization_mode": game.normalization_mode,
        "source_path": game.source_path,
        "is_new": game.is_new,
        "pending_add": game.pending_add,
        "pending_delete": game.pending_delete,
        "has_placeholder_cover": game.has_placeholder_cover,
        "save_status": game.save_status,
    }

