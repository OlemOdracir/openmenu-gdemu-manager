import json
import zipfile
from pathlib import Path
from importlib.resources import files

from PIL import Image
import pytest

from openmenu_gdemu_manager.ui.theme import ThemeRegistry, install_template_package


def _write_template_zip(path: Path, template_id: str = "sample_theme") -> None:
    image = path.parent / "background.png"
    Image.new("RGB", (8, 8), "#ff7a18").save(image)
    manifest = {
        "id": template_id,
        "name": "Sample Theme",
        "version": "1.0.0",
        "author": "Tests",
        "license": "Test assets",
        "palette": {
            "accent": "#123456",
            "surface": "#ffffff",
        },
        "background": {
            "file": "background.png",
            "opacity": 0.25,
        },
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{template_id}/theme.json", json.dumps(manifest))
        archive.write(image, f"{template_id}/background.png")


def test_install_template_package_from_zip(tmp_path):
    zip_path = tmp_path / "theme.zip"
    template_dir = tmp_path / "_ui_templates"
    _write_template_zip(zip_path)

    package = install_template_package(zip_path, template_dir)
    registry = ThemeRegistry(template_dir)

    assert package.id == "sample_theme"
    assert "sample_theme" in registry.templates
    assert registry.get("sample_theme").palette["accent"] == "#123456"
    assert registry.get("sample_theme").background_path().is_file()


def test_install_template_rejects_path_traversal(tmp_path):
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../theme.json", "{}")

    with pytest.raises(ValueError):
        install_template_package(zip_path, tmp_path / "_ui_templates")


def test_install_template_rejects_executable_files(tmp_path):
    zip_path = tmp_path / "bad_ext.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("bad/theme.json", "{}")
        archive.writestr("bad/run.ps1", "Write-Host bad")

    with pytest.raises(ValueError):
        install_template_package(zip_path, tmp_path / "_ui_templates")


def test_registry_falls_back_to_internal_template(tmp_path):
    registry = ThemeRegistry(tmp_path / "missing")

    assert registry.normalize("does_not_exist") == "arcade_clean"
    assert registry.get("does_not_exist").id == "arcade_clean"


def test_backup_prompt_illustration_is_packaged():
    path = files("openmenu_gdemu_manager.resources.illustrations").joinpath("backup_sd_to_hdd_512.png")

    assert path.is_file()
