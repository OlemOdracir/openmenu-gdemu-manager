import pytest
from PIL import Image

from openmenu_gdemu_manager.dreamcast.openmenu_dat import (
    BOX_ENTRY_SIZE,
    ICON_ENTRY_SIZE,
    DatEntry,
    extract_dat_cover,
    normalize_dat_serial,
    read_dat,
    update_artwork_dats,
    write_dat,
)


def test_normalize_dat_serial_strips_and_truncates():
    assert normalize_dat_serial("T-1234M extra") == "T1234MEXTR"


def test_write_and_read_dat_round_trips_entries(tmp_path):
    path = tmp_path / "BOX.DAT"
    data = b"A" * BOX_ENTRY_SIZE

    write_dat(path, BOX_ENTRY_SIZE, [DatEntry("T1234M", data)])

    entries = read_dat(path, BOX_ENTRY_SIZE)
    assert len(entries) == 1
    assert entries[0].name == "T1234M"
    assert entries[0].data == data


def test_update_artwork_dats_creates_box_and_icon_entries(tmp_path):
    image_path = tmp_path / "cover.png"
    Image.new("RGB", (300, 400), (200, 30, 70)).save(image_path)

    changed = update_artwork_dats(tmp_path, {"T-1234M": image_path})

    assert changed == 1
    box_entries = read_dat(tmp_path / "BOX.DAT", BOX_ENTRY_SIZE)
    icon_entries = read_dat(tmp_path / "ICON.DAT", ICON_ENTRY_SIZE)
    assert [entry.name for entry in box_entries] == ["T1234M"]
    assert [entry.name for entry in icon_entries] == ["T1234M"]
    assert len(box_entries[0].data) == BOX_ENTRY_SIZE
    assert len(icon_entries[0].data) == ICON_ENTRY_SIZE
    assert box_entries[0].data.startswith(b"GBIX")
    assert icon_entries[0].data.startswith(b"GBIX")


def test_extract_dat_cover_writes_png(tmp_path):
    image_path = tmp_path / "cover.png"
    out_path = tmp_path / "out.png"
    Image.new("RGB", (300, 400), (30, 120, 200)).save(image_path)
    update_artwork_dats(tmp_path, {"T-1234M": image_path})
    entries = {entry.name: entry for entry in read_dat(tmp_path / "BOX.DAT", BOX_ENTRY_SIZE)}

    result = extract_dat_cover(entries, "T1234M", out_path)

    assert result == out_path
    assert out_path.exists()
    with Image.open(out_path) as image:
        assert image.size == (256, 256)


def test_read_dat_rejects_wrong_entry_size(tmp_path):
    path = tmp_path / "ICON.DAT"
    write_dat(path, BOX_ENTRY_SIZE, [DatEntry("T1234M", b"A" * BOX_ENTRY_SIZE)])

    with pytest.raises(ValueError, match="esperado"):
        read_dat(path, ICON_ENTRY_SIZE)
