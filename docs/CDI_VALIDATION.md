# Read-only CDI structural validation

## Contract

The CDI validator replaces the non-empty-file check for V2 import, save preflight,
staging verification and transaction recovery. It never extracts, repairs or writes
an image. It shares the existing ImageIntegrityError gate and existing services;
legacy UI write behavior is not silently converted into a new automation path.

Recognized footer profiles: DiscJuggler 2.0 (0x80000004), 3.0 (0x80000005), and
3.5/4.0 (0x80000006). The first two store an absolute descriptor position; the
last stores its distance from EOF. Classic track markers, conditional prefixes,
DJ4 extension, additional index records and bounded CD-TEXT fields are parsed.
Supported stored sector lengths are 2048, 2336, 2352, 2368 and 2448 bytes;
the last two include subchannel data. Their presence does not certify firmware
support. At most 99 sessions, 99 total tracks, 99 indices per track, 99 CD-TEXT
blocks per track and 4 MiB of descriptor bytes are inspected. Exceeding these
limits is unsupported/review, not a corruption claim.

Confirmed structural failures include a short footer, impossible descriptor
position, a bounded descriptor read that runs out of bytes, empty tracks,
index lengths greater than the declared track length, and track extents entering
the descriptor or extending past the file. Extents include stored pregaps and
subchannels; the validator does not compare a CDI to external GDI tracks.
Unknown versions, unknown markers/layouts, historical signed short-track indices
and unsupported sector/index modes
are distinct review failures. Read/access errors and detected changes during
inspection are reported separately. All three categories block a new V2 import
until the source can be verified; review does not mean the disc is corrupt.

Payload bytes are not scanned or checksummed by this parser. Disc-level metadata
after the sessions is opaque. Unreferenced payload padding is reported, not
rejected. Filesystem extents, EDC, trusted-reference checksums, exotic layouts,
firmware interpretation and actual game boot remain separate work/evidence.
Successful validation means the supported descriptor's declared extents fit;
it is not a statement that a game works on Dreamcast.

## Format evidence and provenance

The implementation is original Python code using the independently published
format observations in these primary parser sources, inspected 2026-10-09:

- [CDIrip CDI parser](https://github.com/jozip/cdirip/blob/master/cdi.c) and
  [version declarations](https://github.com/jozip/cdirip/blob/master/cdi.h).
  GPL-2.0 repository; no CDIrip code or executable is bundled.
- [libMirage CDI parser](https://github.com/cdemu/cdemu/blob/master/libmirage/images/image-cdi/parser.c).
  GPL-2.0-or-later header; no libMirage code, library or executable is bundled.

No binary dependency is added. Research copies stay in ignored build artifacts.
The format is reverse engineered; unknown fields are not given invented meanings.

## Local acceptance evidence

Generated fixtures contain zero-filled payloads and synthetic metadata, no ROMs.
The classic builder follows versioned CDIrip framing; an independently constructed
modern builder follows libMirage session/header/tail framing. Cases cover three
versions, multiple sessions/tracks, pregaps, extra prefixes, DJ4 data, CD-TEXT,
additional indices, subchannels, byte/whole-sector truncation, bounded malformed
input and EN/ES presentation. Tests also cover mixed GDI/CDI folders and preserve
existing slots/menu/configuration on invalid preflight. Equal-byte-count staging
damage blocks publishing and recovery completion; reversal remains possible.

The generated full regression report is [V2_VALIDATION.md](V2_VALIDATION.md).
Independent audit status is recorded separately after review. These fixtures are
not a hardware test or validation of all real-world CDI variants.
