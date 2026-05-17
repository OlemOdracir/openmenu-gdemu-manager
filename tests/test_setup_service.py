from pathlib import Path

import openmenu_gdemu_manager.services.setup_service as setup_service


def test_install_openmenu_base_falls_back_to_rebuilder_when_template_dir_missing(monkeypatch, tmp_path):
    root = tmp_path / "sd"
    root.mkdir(parents=True)
    settings = {
        "openmenu_setup": {
            "template_dir": "_OpenMenuBuildMissing",
        }
    }

    def _fake_prepare_empty_base(self, staging_root: Path) -> Path:
        slot = Path(staging_root) / "01"
        slot.mkdir(parents=True, exist_ok=True)
        (slot / "disc.gdi").write_text("fake", encoding="ascii")
        return slot

    monkeypatch.setattr(setup_service.OpenMenuRebuilder, "prepare_empty_base", _fake_prepare_empty_base)

    diagnostic = setup_service.install_openmenu_base(root, settings=settings)

    assert (root / "01" / "disc.gdi").exists()
    assert diagnostic.scan_allowed is True
