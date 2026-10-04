"""Approved sprite-only handoff, applied after original-layout cast patches."""
import importlib.util
from pathlib import Path
from cam_io import Entry, name

HANDOFF = Path(__file__).resolve().parents[1]/'art/spellsinger-world-v1/handoff-r1'
TILE_COUNT = 681
SOURCE_COMMIT = '74b6f3da338335b1314bb8ffbd0ef46f67a3a3a6'


def adapter():
    spec = importlib.util.spec_from_file_location('bards_spellsinger_importer', HANDOFF/'import_sprite.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.verify(HANDOFF)
    return module


def append_art(images, tiles, palettes):
    matches = [i for i,e in enumerate(images) if e.name.rstrip(b'\0') == b'BDS1Spellsinger']
    if len(matches) != 1:
        raise ValueError('Expected exactly one Spellsinger descriptor')
    index, tile_start, palette_start = matches[0], len(tiles), len(palettes)
    imag, new_tiles, new_palettes, report = adapter().integrate(
        images[index].data, HANDOFF, tile_start=tile_start,
        hero_palette_index=palette_start, dead_palette_index=palette_start+1)
    assert len(new_tiles) == TILE_COUNT and len(new_palettes) == 2
    for existing, additions in ((tiles,new_tiles),(palettes,new_palettes)):
        names = {e.name for e in existing}
        for label,data in additions:
            key = name(label.encode())
            if key in names:
                raise ValueError('Spellsinger resource collision: '+label)
            names.add(key)
            existing.append(Entry(key,data))
    images[index] = Entry(images[index].name,imag)
    return dict(report, tile_start=tile_start, palette_start=palette_start,
                tile_count=len(new_tiles),source_commit=SOURCE_COMMIT)
