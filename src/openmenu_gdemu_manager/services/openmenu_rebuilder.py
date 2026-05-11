from __future__ import annotations

import shutil
import subprocess
import tempfile
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..config.paths import BACKUPS_DIR
from ..config.settings import (
    configured_buildgdi_expected_sha256,
    configured_buildgdi_expected_version,
    configured_buildgdi_path,
    configured_menu_data_dir,
    configured_menu_gdi_dir,
    load_settings,
)
from ..core.models import GameItem
from ..dreamcast.openmenu_dat import BOX_ENTRY_SIZE, normalize_dat_serial, read_dat_by_name, update_artwork_dats
from ..dreamcast.metadata import is_synthetic_slot_serial, read_disc_product_id
from ..dreamcast.sd_writer import build_openmenu_text


class OpenMenuRebuildError(RuntimeError):
    """Raised when the openMenu GDI rebuild cannot be completed safely."""


@dataclass(frozen=True)
class OpenMenuRebuildConfig:
    buildgdi_path: Path
    menu_gdi_dir: Path
    menu_data_dir: Path | None = None
    backup_dir: Path = BACKUPS_DIR / "MenuRebuild"
    expected_buildgdi_version: str = ""
    expected_buildgdi_sha256: str = ""


@dataclass(frozen=True)
class OpenMenuRebuildResult:
    staging_slot: Path
    backup_slot: Path
    num_items: int


class OpenMenuRebuilder:
    def __init__(self, config: OpenMenuRebuildConfig | None = None):
        self.config = config or config_from_settings()

    def rebuild_and_replace(self, root_path: Path, games: list[GameItem]) -> OpenMenuRebuildResult:
        root_path = Path(root_path)
        final_games = sorted([game for game in games if not game.pending_delete], key=lambda game: game.slot)
        with tempfile.TemporaryDirectory(prefix="openmenu_rebuild_") as tmp_raw:
            tmp = Path(tmp_raw)
            staging_slot = self.prepare_staging(root_path, final_games, tmp)
            backup_slot = self.replace_slot_01(root_path, staging_slot)
            return OpenMenuRebuildResult(
                staging_slot=staging_slot,
                backup_slot=backup_slot,
                num_items=len(final_games),
            )

    def prepare_staging(self, root_path: Path, games: list[GameItem], staging_root: Path) -> Path:
        self._validate_config()
        root_path = Path(root_path)
        staging_root = Path(staging_root)
        data_dir = staging_root / "data"
        output_slot = staging_root / "01"

        current_gdi = root_path / "01" / "disc.gdi"
        if not current_gdi.exists():
            raise OpenMenuRebuildError(f"No se encontro el descriptor GDI actual: {current_gdi}")

        shutil.copytree(self.config.menu_gdi_dir, output_slot, dirs_exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        self._extract_current_menu(current_gdi, data_dir)
        self._complete_missing_menu_data(data_dir)
        (data_dir / "OPENMENU.INI").write_text(build_openmenu_text(games, newline="\r\n"), encoding="latin-1", errors="replace")
        self._update_artwork(data_dir, games)

        ip_bin = data_dir / "IP.BIN"
        cdda = output_slot / "track04.raw"
        gdi = output_slot / "disc.gdi"
        command = [
            str(self.config.buildgdi_path),
            "-data", str(data_dir),
            "-ip", str(ip_bin),
            "-cdda", str(cdda),
            "-output", str(output_slot),
            "-gdi", str(gdi),
            "-iso",
            "-truncate",
        ]
        result = _run_buildgdi(command, cwd=staging_root)
        if result.returncode != 0:
            raise OpenMenuRebuildError(_command_error("buildgdi fallo al reconstruir openMenu", result))

        obsolete_track03_iso = output_slot / "track03.iso"
        if obsolete_track03_iso.exists() and "track03.iso" not in self._declared_gdi_files(gdi):
            obsolete_track03_iso.unlink()

        validate_rebuilt_slot(output_slot, expected_items=len(games))
        return output_slot

    def replace_slot_01(self, root_path: Path, staging_slot: Path) -> Path:
        root_path = Path(root_path)
        staging_slot = Path(staging_slot)
        current_slot = root_path / "01"
        if not current_slot.is_dir():
            raise OpenMenuRebuildError(f"No se encontro el slot 01 actual: {current_slot}")
        validate_rebuilt_slot(staging_slot)

        backup_slot = self._backup_slot_01(root_path, current_slot)
        try:
            shutil.rmtree(current_slot)
            shutil.copytree(staging_slot, current_slot)
            validate_rebuilt_slot(current_slot)
        except Exception as exc:
            if current_slot.exists():
                shutil.rmtree(current_slot, ignore_errors=True)
            shutil.copytree(backup_slot, current_slot)
            raise OpenMenuRebuildError(f"No se pudo reemplazar 01; se restauro el backup: {backup_slot}") from exc
        return backup_slot

    def _validate_config(self) -> None:
        if not self.config.buildgdi_path.is_file():
            raise OpenMenuRebuildError(f"No se encontro buildgdi.exe: {self.config.buildgdi_path}")
        expected_hash = self.config.expected_buildgdi_sha256.strip().upper()
        if expected_hash:
            actual_hash = _sha256_file(self.config.buildgdi_path)
            if actual_hash != expected_hash:
                raise OpenMenuRebuildError(
                    "buildgdi.exe no coincide con la version validada. "
                    f"Esperado SHA256 {expected_hash}, obtenido {actual_hash}: {self.config.buildgdi_path}"
                )
        expected_version = self.config.expected_buildgdi_version.strip()
        if expected_version:
            result = _run_buildgdi([str(self.config.buildgdi_path)])
            output = "\n".join(part for part in (result.stdout, result.stderr) if part)
            if expected_version not in output:
                raise OpenMenuRebuildError(
                    "buildgdi.exe no reporta la version validada. "
                    f"Esperado '{expected_version}': {self.config.buildgdi_path}"
                )
        if not self.config.menu_gdi_dir.is_dir():
            raise OpenMenuRebuildError(f"No se encontro menu_gdi: {self.config.menu_gdi_dir}")
        for name in ("disc.gdi", "track01.iso", "track02.raw", "track04.raw"):
            if not (self.config.menu_gdi_dir / name).exists():
                raise OpenMenuRebuildError(f"La plantilla menu_gdi no contiene {name}: {self.config.menu_gdi_dir}")

    def _extract_current_menu(self, current_gdi: Path, data_dir: Path) -> None:
        command = [
            str(self.config.buildgdi_path),
            "-extract",
            "-gdi", str(current_gdi),
            "-output", str(data_dir),
            "-ip", str(data_dir / "IP.BIN"),
        ]
        result = _run_buildgdi(command, cwd=current_gdi.parent)
        required = ("IP.BIN", "1ST_READ.BIN", "OPENMENU.INI")
        if result.returncode != 0 and not all((data_dir / name).exists() for name in required):
            raise OpenMenuRebuildError(_command_error("buildgdi fallo al extraer el menu actual", result))
        for name in required:
            if not (data_dir / name).exists():
                raise OpenMenuRebuildError(f"La extraccion no genero {name}")

    def _complete_missing_menu_data(self, data_dir: Path) -> None:
        source = self.config.menu_data_dir
        if not source or not source.is_dir():
            return
        for path in source.rglob("*"):
            relative = path.relative_to(source)
            target = data_dir / relative
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)

    def _update_artwork(self, data_dir: Path, games: list[GameItem]) -> int:
        updates: dict[str, Path] = {}
        existing_box_serials = _existing_box_serials(data_dir)
        for game in games:
            if game.pending_delete or game.has_placeholder_cover:
                continue
            serials = _artwork_serial_aliases(game)
            if not serials:
                continue
            selected_path = _existing_path(game.selected_image)
            if selected_path is not None:
                for serial in serials:
                    updates[serial] = selected_path
                continue
            if any(serial not in existing_box_serials for serial in serials):
                current_path = _existing_path(game.current_cover)
                if current_path is not None:
                    for serial in serials:
                        updates[serial] = current_path
        if not updates:
            return 0
        return update_artwork_dats(data_dir, updates)

    def _backup_slot_01(self, root_path: Path, current_slot: Path) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        label = root_path.anchor.replace(":\\", "").replace("\\", "") or root_path.name or "sd"
        backup_slot = self.config.backup_dir / f"01-before-rebuild-{label}-{timestamp}"
        backup_slot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(current_slot, backup_slot)
        return backup_slot

    @staticmethod
    def _declared_gdi_files(gdi_path: Path) -> set[str]:
        return _declared_gdi_files(gdi_path)


def config_from_settings(settings: dict | None = None) -> OpenMenuRebuildConfig:
    settings = settings or load_settings()
    menu_data_dir = configured_menu_data_dir(settings)
    return OpenMenuRebuildConfig(
        buildgdi_path=configured_buildgdi_path(settings),
        menu_gdi_dir=configured_menu_gdi_dir(settings),
        menu_data_dir=menu_data_dir if str(menu_data_dir) else None,
        expected_buildgdi_version=configured_buildgdi_expected_version(settings),
        expected_buildgdi_sha256=configured_buildgdi_expected_sha256(settings),
    )


def validate_rebuilt_slot(slot_path: Path, expected_items: int | None = None) -> None:
    slot_path = Path(slot_path)
    gdi = slot_path / "disc.gdi"
    if not gdi.exists():
        raise OpenMenuRebuildError(f"No se genero disc.gdi: {gdi}")
    declared = _declared_gdi_files(gdi)
    if not declared:
        raise OpenMenuRebuildError(f"disc.gdi no declara tracks validos: {gdi}")
    missing = sorted(name for name in declared if not (slot_path / name).exists())
    if missing:
        raise OpenMenuRebuildError(f"Faltan tracks declarados por disc.gdi: {', '.join(missing)}")
    data_track = _last_data_track(slot_path, declared)
    data = data_track.read_bytes()
    if b"[OPENMENU]" not in data:
        raise OpenMenuRebuildError(f"No se encontro [OPENMENU] en {data_track.name}")
    if expected_items is not None:
        expected = f"num_items={expected_items}".encode("ascii")
        if expected not in data:
            raise OpenMenuRebuildError(f"No se encontro {expected.decode()} en {data_track.name}")


def _declared_gdi_files(gdi_path: Path) -> set[str]:
    lines = gdi_path.read_text(encoding="ascii", errors="replace").splitlines()
    result: set[str] = set()
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 5:
            result.add(parts[4])
    return result


def _last_data_track(slot_path: Path, declared: set[str]) -> Path:
    candidates = [slot_path / name for name in declared if name.lower().endswith((".bin", ".iso"))]
    if not candidates:
        raise OpenMenuRebuildError("disc.gdi no declara tracks de datos")
    return max(candidates, key=lambda path: path.stat().st_size)


def _command_error(message: str, result: subprocess.CompletedProcess[str]) -> str:
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())
    if output:
        return f"{message} (codigo {result.returncode}).\n{output}"
    return f"{message} (codigo {result.returncode})."


def _existing_box_serials(data_dir: Path) -> set[str]:
    try:
        return set(read_dat_by_name(Path(data_dir) / "BOX.DAT", BOX_ENTRY_SIZE))
    except Exception:
        return set()


def _existing_path(value: str | Path | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def _artwork_serial_aliases(game: GameItem) -> list[str]:
    aliases: list[str] = []
    for serial in game.artwork_serials:
        _append_serial_alias(aliases, serial)
    _append_serial_alias(aliases, game.product_id)
    if is_synthetic_slot_serial(game.product_id):
        _append_serial_alias(aliases, f"SLOT{game.slot:03d}")
    elif not game.product_id:
        _append_serial_alias(aliases, f"SLOT{game.slot:03d}")
    _append_serial_alias(aliases, read_disc_product_id(game.folder))
    return aliases


def _append_serial_alias(aliases: list[str], serial: str | None) -> None:
    normalized = normalize_dat_serial(serial or "")
    if normalized and normalized not in aliases:
        aliases.append(normalized)


def _run_buildgdi(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    kwargs = {"capture_output": True, "text": True}
    if cwd:
        kwargs["cwd"] = str(cwd)
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(command, **kwargs)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()
