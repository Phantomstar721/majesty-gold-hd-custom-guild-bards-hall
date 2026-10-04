"""Apply the locked sprite-pipeline handoff after all Healer-layout patches."""
from pathlib import Path
import sys
import types

from cam_io import Entry, name

HANDOFF = Path(__file__).resolve().parents[1] / 'art/blade-dancer-world-v1/handoff-r2'


def adapter():
    # Execute the exact verified handoff tools without writing into its sealed
    # file inventory or colliding with another sprite verifier's module name.
    verifier = types.ModuleType('verify_handoff')
    verifier.__file__ = str(HANDOFF / 'verify_handoff.py')
    exec(compile(Path(verifier.__file__).read_bytes(), verifier.__file__, 'exec'), verifier.__dict__)
    verifier.verify(HANDOFF)
    previous = sys.modules.get('verify_handoff')
    sys.modules['verify_handoff'] = verifier
    try:
        module = types.ModuleType('bards_dancer_sprite_importer')
        module.__file__ = str(HANDOFF / 'import_sprite.py')
        exec(compile(Path(module.__file__).read_bytes(), module.__file__, 'exec'), module.__dict__)
        return module
    finally:
        if previous is None:
            del sys.modules['verify_handoff']
        else:
            sys.modules['verify_handoff'] = previous


def append_art(images, tiles, palettes):
    matches = [i for i, entry in enumerate(images) if entry.name.rstrip(b'\0') == b'BDD1Blade_Dancer']
    if len(matches) != 1:
        raise ValueError('Expected exactly one Blade Dancer sprite descriptor')
    index, tile_start, palette_start = matches[0], len(tiles), len(palettes)
    imag, new_tiles, new_palettes, report = adapter().integrate(
        images[index].data, HANDOFF, tile_start=tile_start,
        hero_palette_index=palette_start, dead_palette_index=palette_start + 1)
    assert len(new_tiles) == 1017 and len(new_palettes) == 2
    for existing, additions in ((tiles, new_tiles), (palettes, new_palettes)):
        names = {e.name for e in existing}
        for label, data in additions:
            key = name(label.encode())
            if key in names:
                raise ValueError(f'Blade Dancer resource collision: {label}')
            names.add(key)
            existing.append(Entry(key, data))
    images[index] = Entry(images[index].name, imag)
    return dict(report, tile_start=tile_start, palette_start=palette_start,
                tile_count=len(new_tiles), source_commit='e9cf96c3edec96a1f367dad85caa0b9b91199300')
