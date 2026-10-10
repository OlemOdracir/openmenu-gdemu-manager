"""Structural source checks. These do not certify a disc can boot on hardware."""
import shlex
from pathlib import Path


from .image_errors import ImageIntegrityError
from .cdi import inspect_cdi


def validate_source(source):
    path=Path(source)
    if not path.exists():raise ImageIntegrityError(f'Source missing: {path}')
    descriptors=[path] if path.is_file() and path.suffix.lower()=='.gdi' else list(path.glob('*.gdi')) if path.is_dir() else []
    for descriptor in descriptors:validate_gdi(descriptor)
    cdis=[path] if path.is_file() and path.suffix.lower()=='.cdi' else list(path.glob('*.cdi')) if path.is_dir() else []
    if not descriptors and not cdis:raise ImageIntegrityError(f'No GDI/CDI image found: {path}')
    for cdi in cdis:
        inspect_cdi(cdi)


def validate_gdi(descriptor):
    descriptor=Path(descriptor)
    try:
        lines=[line.strip() for line in descriptor.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        count=int(lines[0])
        if count<1 or len(lines)!=count+1:raise ValueError('track count')
        records=[]
        root=descriptor.parent.resolve()
        for expected,line in enumerate(lines[1:],1):
            fields=shlex.split(line)
            if len(fields)!=6:raise ValueError('track fields')
            number,lba,kind,sector=int(fields[0]),int(fields[1]),int(fields[2]),int(fields[3])
            offset=int(fields[5])
            if number!=expected or lba<0 or kind not in (0,4) or sector not in (2048,2336,2352) or offset<0:raise ValueError('track layout')
            name=fields[4]
            if Path(name).is_absolute() or ':' in name or '\\' in name:raise ValueError('track path')
            track=(root/name).resolve()
            if not track.is_relative_to(root):raise ValueError('track outside source')
            if not track.is_file():raise ImageIntegrityError(f'{descriptor.name}: missing track {name}')
            length=track.stat().st_size-offset
            if length<=0:raise ImageIntegrityError(f'{descriptor.name}: empty track {name}')
            if length%sector:raise ImageIntegrityError(f'{descriptor.name}: incomplete sector in {name}')
            if records and lba<=records[-1][0]:raise ValueError('track order')
            records.append((lba,kind,sector,track,offset,length))
        # Inspect a supported ISO9660 PVD when present. Whole-sector truncation
        # is provable if the advertised filesystem exceeds the stored data.
        data_end=max(lba+length//sector for lba,kind,sector,_,_,length in records if kind==4) if any(record[1]==4 for record in records) else 0
        for lba,kind,sector,track,offset,length in records:
            if kind!=4 or sector not in (2048,2352):continue
            prefix=16 if sector==2352 else 0
            with track.open('rb') as stream:
                stream.seek(offset+16*sector+prefix)
                pvd=stream.read(2048)
            if len(pvd)>=84 and pvd[:7]==b'\x01CD001\x01':
                blocks=int.from_bytes(pvd[80:84],'little')
                # A multisession volume can advertise absolute disc addresses
                # and span multiple data tracks. Never compare that value with
                # the length of only the track holding its PVD. Accept either
                # plausible address convention; reject only a provable overrun.
                possible_ends=[lba+blocks]
                if blocks>=lba:possible_ends.append(blocks)
                if min(possible_ends)>data_end:raise ImageIntegrityError(f'{descriptor.name}: filesystem extends beyond declared data tracks ({track.name})')
    except ImageIntegrityError:raise
    except (OSError,UnicodeError,ValueError,IndexError) as exc:
        raise ImageIntegrityError(f'{descriptor.name}: invalid GDI ({exc})') from exc
