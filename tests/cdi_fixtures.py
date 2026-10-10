"""Generated CDI descriptors, no copyrighted disc payloads.

The modern fixture follows libMirage's session/header/index/track layout.
The classic fixture follows the older documented CDIrip versioned layout.
These independent constructions exercise the same track extent interpretation.
"""
import struct


def u16(value): return struct.pack('<H', value)
def u32(value): return struct.pack('<I', value)
MARK = bytes.fromhex('000001000000ffffffff')
SIZES = (2048, 2336, 2352, 2368, 2448)


def classic_cdi(path, version=0x80000006, sessions=None, *, prefix_extra=False,
                dj4=False, long_tail=False, payload_cut=0, padding=0):
    sessions = sessions or [[{}]]
    descriptor = bytearray(u16(len(sessions)))
    payload = 0
    for tracks in sessions:
        descriptor += u16(len(tracks))
        for track in tracks:
            mode, read_mode = track.get('mode', 1), track.get('read_mode', 0)
            sectors = track.get('sectors', 3)
            indices = track.get('indices', (1, sectors - 1))
            text = track.get('cdtext', [])
            descriptor += u32(1 if prefix_extra else 0)
            if prefix_extra: descriptor += bytes(8)
            descriptor += MARK * 2 + bytes(4) + b'\x08disc.cdi' + bytes(19)
            descriptor += u32(0x80000000 if dj4 else 0)
            if dj4: descriptor += bytes(8)
            descriptor += u16(len(indices)) + b''.join(u32(n) for n in indices)
            descriptor += u32(len(text))
            for block in text:
                for field in block: descriptor += bytes([len(field)]) + field
            descriptor += bytes(2) + u32(mode) + bytes(12) + u32(track.get('lba', 0))
            descriptor += u32(sectors) + bytes(16) + u32(read_mode) + bytes(29)
            if version != 0x80000004:
                descriptor += bytes(5) + u32(0xffffffff if long_tail else 0)
                if long_tail: descriptor += bytes(78)
            payload += sectors * SIZES[read_mode] if read_mode < len(SIZES) else sectors * 2352
        descriptor += bytes(12 if version == 0x80000004 else 13)
    # Opaque disc-level metadata is not interpreted by the structural validator.
    descriptor += bytes(32)
    stored_payload = max(0, payload - payload_cut) + padding
    position = len(descriptor) + 8 if version == 0x80000006 else stored_payload
    path.write_bytes(bytes(stored_payload) + descriptor + u32(version) + u32(position))
    return path


def modern_cdi(path, sessions=None, *, payload_cut=0):
    sessions = sessions or [[{'mode': 0, 'read_mode': 2}], [{}]]
    all_tracks = sum(map(len, sessions))
    descriptor = bytearray([len(sessions)])
    payload = 0
    def header():
        pre = bytearray.fromhex('ffff000001000000ffffffff00000000')
        pre[15] = all_tracks
        post = bytearray(29); post[11] = 2; post[22] = 0x80
        return pre + b'\x08disc.cdi' + post + u16(0x98)
    for tracks in sessions:
        session = bytearray(15); session[1] = len(tracks); session[9] = 1; session[13:15] = b'\xff\xff'
        descriptor += session
        for i, track in enumerate(tracks):
            sectors, mode, read = track.get('sectors', 3), track.get('mode', 1), track.get('read_mode', 0)
            indices = track.get('indices', (1, sectors - 1))
            descriptor += header() + u16(len(indices)) + b''.join(u32(n) for n in indices)
            descriptor += u32(0) + bytes(2) + u32(mode) + bytes(4)
            descriptor += u32(len(sessions)-1) + u32(i) + u32(0) + u32(sectors) + bytes(16)
            descriptor += u32(read) + u32(0) + bytes(9) + bytes(12) + u32(0)
            tail = bytearray(99); tail[1:9] = b'\xff' * 8
            if i < len(tracks) - 1:
                tail[93] = 1; tail[95:99] = b'\x00\x00\xff\xff'
            descriptor += tail
            payload += sectors * SIZES[read]
    end_session = bytearray(15); end_session[9] = 1; end_session[13:15] = b'\xff\xff'
    descriptor += end_session
    descriptor += header() + u32(0) + b'\x00' + bytes(9) + bytes(13) + u32(0) + u32(0) + bytes(8)
    descriptor += u32(0x80000006)
    descriptor += u32(len(descriptor) + 4)
    path.write_bytes(bytes(payload-payload_cut) + descriptor)
    return path
