from pathlib import Path

from openmenu_gdemu_manager.dreamcast.rom_library import inspect_source, is_gdemu_menu_slot


def _ip_bin(product: str, internal_name: str = "") -> bytes:
    ip = bytearray(0x100)
    ip[:16] = b"SEGA SEGAKATANA "
    ip[0x40:0x50] = product.encode("ascii").ljust(0x10, b" ")
    ip[0x80:0x100] = internal_name.encode("ascii").ljust(0x80, b" ")
    return bytes(ip)


def test_inspect_gdi_folder_reads_product_id_from_disc_header(tmp_path):
    folder = tmp_path / "Ecco"
    folder.mkdir()
    (folder / "disc.gdi").write_text(
        "\n".join(["1", "1 45000 4 2048 track03.iso 0"]),
        encoding="ascii",
    )
    (folder / "track03.iso").write_bytes(_ip_bin("MK51033"))

    entry = inspect_source(folder, {"GDI"}, known={})

    assert entry is not None
    assert entry.product_id == "MK51033"


def test_inspect_cdi_file_reads_product_id_from_embedded_ip_bin(tmp_path):
    path = tmp_path / "Half-Life.cdi"
    path.write_bytes(b"\x00" * 4096 + _ip_bin("MK51035"))

    entry = inspect_source(path, {"CDI"}, known={})

    assert entry is not None
    assert entry.product_id == "MK51035"


def test_inspect_numeric_folder_uses_descriptive_cdi_filename(tmp_path):
    folder = tmp_path / "23"
    folder.mkdir()
    (folder / "Crazy Taxi.cdi").write_bytes(b"\x00" * 4096 + _ip_bin("MK51035"))

    entry = inspect_source(folder, {"CDI"}, known={})

    assert entry is not None
    assert entry.name == "Crazy Taxi"


def test_inspect_numeric_folder_uses_internal_name_when_cdi_filename_is_generic(tmp_path):
    folder = tmp_path / "24"
    folder.mkdir()
    (folder / "disc.cdi").write_bytes(b"\x00" * 4096 + _ip_bin("T8109N", "RE-VOLT"))

    entry = inspect_source(folder, {"CDI"}, known={})

    assert entry is not None
    assert entry.name == "RE-VOLT"


def test_inspect_source_ignores_gdemu_menu_slot_with_gdmenu_cdi(tmp_path):
    menu = tmp_path / "01"
    menu.mkdir()
    (menu / "GDmenu_v0.6.cdi").write_bytes(b"\x00" * 4096 + _ip_bin("MK6969"))

    assert inspect_source(menu, {"CDI"}, known={}) is None
    assert inspect_source(menu / "GDmenu_v0.6.cdi", {"CDI"}, known={}) is None


def test_inspect_source_ignores_openmenu_slot_01_gdi(tmp_path):
    menu = tmp_path / "01"
    menu.mkdir()
    (menu / "disc.gdi").write_text(
        "\n".join(["5", "5 487808 4 2048 track05.iso 0"]),
        encoding="ascii",
    )
    (menu / "track05.iso").write_bytes(b"[OPENMENU]\n")

    assert inspect_source(menu, {"GDI"}, known={}) is None


def test_menu_slot_detector_only_matches_slot_01_menu(tmp_path):
    menu = tmp_path / "01"
    menu.mkdir()
    (menu / "disc.gdi").write_text(
        "\n".join(["5", "5 487808 4 2048 track05.iso 0"]),
        encoding="ascii",
    )
    (menu / "track05.iso").write_bytes(b"[OPENMENU]\n")

    game = tmp_path / "02"
    game.mkdir()
    (game / "disc.gdi").write_text(
        "\n".join(["1", "1 45000 4 2048 track03.iso 0"]),
        encoding="ascii",
    )
    (game / "track03.iso").write_bytes(_ip_bin("MK51033"))

    assert is_gdemu_menu_slot(menu)
    assert not is_gdemu_menu_slot(game)
