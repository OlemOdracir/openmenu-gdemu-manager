from pathlib import Path

from openmenu_gdemu_manager.dreamcast.rom_library import inspect_source


def _ip_bin(product: str) -> bytes:
    ip = bytearray(0x100)
    ip[:16] = b"SEGA SEGAKATANA "
    ip[0x40:0x50] = product.encode("ascii").ljust(0x10, b" ")
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
