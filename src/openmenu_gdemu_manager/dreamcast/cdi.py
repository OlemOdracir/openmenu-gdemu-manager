"""Bounded, read-only DiscJuggler track-descriptor inspection.

Format references (no external parser/binary bundled):
https://github.com/jozip/cdirip/blob/master/cdi.c
https://github.com/cdemu/cdemu/blob/master/libmirage/images/image-cdi/parser.c
See docs/CDI_VALIDATION.md for supported profiles and limits.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import struct

from .image_errors import ImageIntegrityError

VERSIONS = {0x80000004: '2.0', 0x80000005: '3.0', 0x80000006: '3.5/4.0'}
SECTOR_SIZES = {0: 2048, 1: 2336, 2: 2352, 3: 2368, 4: 2448}
TRACK_MARK = bytes.fromhex('000001000000ffffffff')
MAX_DESCRIPTOR_BYTES = 4 * 1024 * 1024
MAX_TRACKS = 99
MAX_SESSIONS = 99
MAX_INDICES = 99
MAX_CDTEXT_BLOCKS = 99


class CDIError(ImageIntegrityError):
    """Stable category/code for agents, translated presentation for the GUI."""
    def __init__(self, path, category, code):
        self.path = Path(path)
        self.category = category
        self.code = code
        super().__init__(f'{self.path.name}: CDI {category} ({code})')

    def __str__(self):
        from ..i18n import tr
        return tr('image.cdi.' + self.category, filename=self.path.name,
                  reason=tr('image.cdi.reason.' + self.code))


@dataclass(frozen=True)
class CDITrack:
    session: int
    number: int
    mode: int
    sector_size: int
    start_lba: int
    sectors: int
    indices: tuple[int, ...]
    byte_offset: int
    byte_length: int


@dataclass(frozen=True)
class CDIInspection:
    version: str
    file_bytes: int
    descriptor_offset: int
    descriptor_bytes: int
    sessions: int
    tracks: tuple[CDITrack, ...]
    unreferenced_payload_bytes: int


class _Descriptor:
    def __init__(self, data, path):
        self.data = data
        self.pos = 0
        self.path = path

    def take(self, size):
        if size < 0 or self.pos + size > len(self.data):
            raise CDIError(self.path, 'invalid', 'descriptor_truncated')
        start = self.pos
        self.pos += size
        return self.data[start:self.pos]

    def skip(self, size):
        self.take(size)

    def integer(self, width):
        return int.from_bytes(self.take(width), 'little')


def _track(reader, version, session, number, offset, payload_end):
    # Classic descriptors overlap their session tails with the two start marks.
    # The conditional prefix and DJ4 extension are part of that profile.
    if reader.integer(4):
        reader.skip(8)
    if reader.take(10) != TRACK_MARK or reader.take(10) != TRACK_MARK:
        raise CDIError(reader.path, 'unsupported', 'track_layout')
    reader.skip(4)
    reader.skip(reader.integer(1))  # Embedded filename is metadata, never a path.
    reader.skip(19)
    if reader.integer(4) == 0x80000000:
        reader.skip(8)
    count = reader.integer(2)
    if not 2 <= count <= MAX_INDICES:
        raise CDIError(reader.path, 'unsupported', 'index_layout')
    indices = tuple(reader.integer(4) for _ in range(count))
    if any(value & 0x80000000 for value in indices):
        # Some historical short-track layouts use signed index lengths.
        # They need a dedicated interpretation, not a corruption claim.
        raise CDIError(reader.path, 'unsupported', 'index_layout')
    cdtext_blocks = reader.integer(4)
    if cdtext_blocks > MAX_CDTEXT_BLOCKS:
        raise CDIError(reader.path, 'unsupported', 'resource_limit')
    for _ in range(cdtext_blocks):
        for _ in range(18):
            reader.skip(reader.integer(1))
    reader.skip(2)
    mode = reader.integer(4)
    reader.skip(12)
    lba = reader.integer(4)
    sectors = reader.integer(4)
    reader.skip(16)
    read_mode = reader.integer(4)
    if mode not in (0, 1, 2) or read_mode not in SECTOR_SIZES:
        raise CDIError(reader.path, 'unsupported', 'sector_layout')
    if (read_mode == 0 and mode != 1) or (read_mode == 1 and mode != 2):
        raise CDIError(reader.path, 'unsupported', 'sector_layout')
    if sectors == 0 or not any(indices[1:]):
        raise CDIError(reader.path, 'invalid', 'empty_track')
    if sum(indices) > sectors:
        raise CDIError(reader.path, 'invalid', 'index_bounds')
    size = SECTOR_SIZES[read_mode]
    length = sectors * size
    if offset + length > payload_end:
        raise CDIError(reader.path, 'invalid', 'track_bounds')
    reader.skip(29)
    if version != 0x80000004:
        reader.skip(5)
        if reader.integer(4) == 0xffffffff:
            reader.skip(78)
    return CDITrack(session, number, mode, size, lba, sectors, indices, offset, length)


def inspect_cdi(path):
    """Validate descriptor reads and declared track extents, without extraction.

    Success is structural evidence only: payload checksums, filesystem contents,
    firmware compatibility and Dreamcast bootability are not certified.
    Unknown layouts raise category 'unsupported', not 'invalid'.
    """
    path = Path(path)
    try:
        with path.open('rb') as stream:
            before = os.fstat(stream.fileno())
            size = before.st_size
            if size < 8:
                raise CDIError(path, 'invalid', 'file_short')
            stream.seek(size - 8)
            footer = stream.read(8)
            if len(footer) != 8:
                raise CDIError(path, 'unreadable', 'changed_file')
            version, position = struct.unpack('<II', footer)
            if version not in VERSIONS:
                raise CDIError(path, 'unsupported', 'version')
            start = size - position if version == 0x80000006 else position
            if start <= 0 or start >= size - 8:
                raise CDIError(path, 'invalid', 'descriptor_position')
            length = size - 8 - start
            if length > MAX_DESCRIPTOR_BYTES:
                raise CDIError(path, 'unsupported', 'resource_limit')
            stream.seek(start)
            data = stream.read(length)
            if len(data) != length:
                raise CDIError(path, 'unreadable', 'changed_file')
            reader = _Descriptor(data, path)
            sessions = reader.integer(2)
            if not 1 <= sessions <= MAX_SESSIONS:
                raise CDIError(path, 'unsupported', 'session_layout')
            tracks = []
            offset = 0
            for session in range(1, sessions + 1):
                count = reader.integer(2)
                if count == 0 or len(tracks) + count > MAX_TRACKS:
                    raise CDIError(path, 'unsupported', 'session_layout')
                for _ in range(count):
                    track = _track(reader, version, session, len(tracks) + 1, offset, start)
                    tracks.append(track)
                    offset += track.byte_length
                reader.skip(12 if version == 0x80000004 else 13)
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise CDIError(path, 'unreadable', 'changed_file')
            return CDIInspection(VERSIONS[version], size, start, length + 8,
                                 sessions, tuple(tracks), start - offset)
    except CDIError:
        raise
    except (OSError, ValueError, OverflowError) as exc:
        raise CDIError(path, 'unreadable', 'read_error') from exc
