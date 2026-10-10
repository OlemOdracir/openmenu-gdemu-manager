from pathlib import Path
import struct
import pytest

from cdi_fixtures import classic_cdi, modern_cdi
from openmenu_gdemu_manager.dreamcast.cdi import inspect_cdi, CDIError, MAX_DESCRIPTOR_BYTES
from openmenu_gdemu_manager.dreamcast.image_integrity import validate_source


@pytest.mark.parametrize('version', [0x80000004, 0x80000005, 0x80000006])
@pytest.mark.parametrize('extras', [False, True])
def test_classic_versioned_descriptors(version, extras, tmp_path):
    path = classic_cdi(tmp_path/'disc.cdi', version, [[{}, {'mode': 2, 'read_mode': 1}], [{'mode': 0, 'read_mode': 2}]],
                       prefix_extra=extras, dj4=extras, long_tail=extras)
    before = path.read_bytes()
    report = inspect_cdi(path)
    assert len(report.tracks) == 3 and report.sessions == 2
    assert [t.sector_size for t in report.tracks] == [2048, 2336, 2352]
    assert report.tracks[1].byte_offset == 6144
    assert sum(t.byte_length for t in report.tracks) == report.descriptor_offset
    validate_source(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize('sessions', [[[{}]], [[{}, {'mode': 0, 'read_mode': 2}], [{'mode': 2, 'read_mode': 1}]]])
def test_independent_modern_descriptor_construction(tmp_path, sessions):
    path = modern_cdi(tmp_path/'disc.cdi', sessions)
    report = inspect_cdi(path)
    assert len(report.tracks) == sum(map(len, sessions))
    assert report.unreferenced_payload_bytes == 0


@pytest.mark.parametrize('read_mode', [2, 3, 4])
@pytest.mark.parametrize('mode', [0, 1, 2])
def test_raw_sectors_with_optional_subchannels(tmp_path, read_mode, mode):
    path = classic_cdi(tmp_path/'disc.cdi', sessions=[[{'mode': mode, 'read_mode': read_mode}]])
    assert inspect_cdi(path).tracks[0].sector_size == (2352, 2368, 2448)[read_mode-2]


@pytest.mark.parametrize('cut', [1, 2048, 4096])
@pytest.mark.parametrize('builder', [classic_cdi, modern_cdi])
def test_declared_track_bounds_prove_truncation(tmp_path, builder, cut):
    path = builder(tmp_path/'disc.cdi', sessions=[[{}]], payload_cut=cut)
    with pytest.raises(CDIError) as error: inspect_cdi(path)
    assert (error.value.category, error.value.code) == ('invalid', 'track_bounds')


@pytest.mark.parametrize('track,code,category', [
    ({'sectors': 0, 'indices': (0, 0)}, 'empty_track', 'invalid'),
    ({'indices': (2, 2)}, 'index_bounds', 'invalid'),
    ({'indices': (1,)}, 'index_layout', 'unsupported'),
    ({'mode': 5}, 'sector_layout', 'unsupported'),
    ({'read_mode': 5}, 'sector_layout', 'unsupported'),
    ({'mode': 0, 'read_mode': 0}, 'sector_layout', 'unsupported'),
    ({'mode': 1, 'read_mode': 1}, 'sector_layout', 'unsupported')])
def test_specific_categories(tmp_path, track, code, category):
    path = classic_cdi(tmp_path/'disc.cdi', sessions=[[track]], padding=1 if track.get('sectors') == 0 else 0)
    with pytest.raises(CDIError) as error: inspect_cdi(path)
    assert (error.value.category, error.value.code) == (category, code)


def test_additional_indices_cdtext_and_padding_are_not_mislabelled_corrupt(tmp_path):
    fields = [b'generated'] + [b''] * 17
    path = classic_cdi(tmp_path/'disc.cdi', sessions=[[{'indices': (0, 1, 2), 'cdtext': [fields]}]], padding=37)
    result = inspect_cdi(path)
    assert result.tracks[0].indices == (0, 1, 2)
    assert result.unreferenced_payload_bytes == 37


@pytest.mark.parametrize('payload,category,code', [
    (b'', 'invalid', 'file_short'), (b'1234567', 'invalid', 'file_short'),
    (struct.pack('<II', 0x80000009, 8), 'unsupported', 'version'),
    (struct.pack('<II', 0x80000006, 0), 'invalid', 'descriptor_position'),
    (struct.pack('<II', 0x80000006, 99), 'invalid', 'descriptor_position')])
def test_bad_footer_and_unknown_version(tmp_path, payload, category, code):
    path = tmp_path/'disc.cdi'; path.write_bytes(payload)
    with pytest.raises(CDIError) as error: inspect_cdi(path)
    assert (error.value.category, error.value.code) == (category, code)


def test_descriptor_reads_are_bounded(tmp_path):
    path = tmp_path/'disc.cdi'
    path.write_bytes(b'x' + b'\x01\x00\x01\x00' + struct.pack('<II', 0x80000006, 12))
    with pytest.raises(CDIError) as error: inspect_cdi(path)
    assert error.value.code == 'descriptor_truncated'
    path.write_bytes(b'x' + bytes(MAX_DESCRIPTOR_BYTES + 1) + struct.pack('<II', 0x80000006, MAX_DESCRIPTOR_BYTES + 9))
    with pytest.raises(CDIError) as error: inspect_cdi(path)
    assert (error.value.category, error.value.code) == ('unsupported', 'resource_limit')


def test_unreadable_source(tmp_path):
    with pytest.raises(CDIError) as error: inspect_cdi(tmp_path/'missing.cdi')
    assert error.value.category == 'unreadable'


@pytest.mark.parametrize('language', ['en', 'es'])
def test_errors_are_localized_with_stable_machine_codes(tmp_path, language):
    from openmenu_gdemu_manager.i18n import set_language
    set_language(language)
    try:
        with pytest.raises(CDIError) as error: inspect_cdi(tmp_path/'missing.cdi')
        message = str(error.value)
        assert message.startswith('No se puede' if language == 'es' else 'Cannot inspect')
        assert 'image.cdi.' not in message and error.value.code == 'read_error'
    finally: set_language('en')


def test_folder_does_not_hide_a_damaged_cdi_behind_valid_gdi(tmp_path):
    folder = tmp_path/'mixed'; folder.mkdir()
    (folder/'disc.gdi').write_text('1\n1 0 4 2048 track.iso 0\n')
    (folder/'track.iso').write_bytes(bytes(2048))
    classic_cdi(folder/'disc.cdi', payload_cut=2048)
    with pytest.raises(CDIError) as error: validate_source(folder)
    assert error.value.code == 'track_bounds'



def test_special_signed_short_track_is_review_not_corruption(tmp_path):
    path = classic_cdi(tmp_path/'disc.cdi', sessions=[[{'indices': (150, 0xffffff6a)}]])
    with pytest.raises(CDIError) as error: inspect_cdi(path)
    assert (error.value.category, error.value.code) == ('unsupported', 'index_layout')
