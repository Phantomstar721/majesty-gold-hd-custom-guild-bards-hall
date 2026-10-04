"""Bake approved Golden Chorus components into stock WRF1's 30-frame loop.

This is offline sprite preparation. Native animation owns playback; there is
no runtime movement controller, timer, or generated sequence of new paintings.
"""
import hashlib
import math
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / 'art/chronicles-effects-v2/golden-chorus-components.png'
MASTER_SHA256 = '754ac3bfc447e319b4052fc369c2ae0ce83fd088d1749330d5ff3fbe3846b62d'
SIZE = (80, 80)
CENTER = (40, 40)
FRAME_COUNT = 30
NOTE_COUNT = 4
RADIUS = (27, 8)
SAMPLE_SCALE = 8


def note_positions(frame):
    """One quarter orbit per native loop; four identical notes tile the seam.

    Each visible step advances three degrees, including frame29 -> frame0.
    A full revolution in 30 frames would move notes over five pixels per step
    at this scale. Four equal, identical notes make a quarter-turn loop exact.
    """
    phase = (frame % FRAME_COUNT) * math.tau / (NOTE_COUNT * FRAME_COUNT)
    return [(CENTER[0] + RADIUS[0]*math.cos(phase + i*math.tau/NOTE_COUNT),
             CENTER[1] + RADIUS[1]*math.sin(phase + i*math.tau/NOTE_COUNT))
            for i in range(NOTE_COUNT)]


def component(source, box, size):
    """Native sprite preparation from the generated black-key source kit."""
    crop = source.crop(box).convert('RGB')
    rgba = Image.new('RGBA', crop.size)
    # World-effect source uses black negative space. Decode its intensity as
    # coverage before resampling, preventing a black matte around thin glyphs.
    values = []
    for rgb in crop.getdata():
        coverage = max(rgb)
        if coverage < 24:
            values.append((0, 0, 0, 0))
        else:
            values.append(tuple(min(255, round(v*255/coverage)) for v in rgb) + (coverage,))
    rgba.putdata(values)
    bounds = rgba.getchannel('A').point(lambda v: 255 if v >= 80 else 0).getbbox()
    if bounds is None:
        raise ValueError('Golden Chorus component is empty')
    left, top, right, bottom = bounds
    bounds = (max(0, left-8), max(0, top-8), min(rgba.width, right+8), min(rgba.height, bottom+8))
    return rgba.crop(bounds).resize(tuple(v*SAMPLE_SCALE for v in size), Image.Resampling.LANCZOS)


def frames():
    if hashlib.sha256(MASTER.read_bytes()).hexdigest() != MASTER_SHA256:
        raise ValueError('Golden Chorus source kit changed without review')
    with Image.open(MASTER) as source:
        cut = round(source.height*0.62)
        ring = component(source, (0, 0, source.width, cut), (64, 22))
        note = component(source, (0, cut, source.width, source.height), (7, 11))
    pictures = []
    for frame in range(FRAME_COUNT):
        canvas = Image.new('RGBA', tuple(v*SAMPLE_SCALE for v in SIZE))
        canvas.alpha_composite(ring, (CENTER[0]*SAMPLE_SCALE-ring.width//2,
                                     CENTER[1]*SAMPLE_SCALE-ring.height//2))
        # Upright, identical glyphs orbit around the fixed ring. Their notehead
        # sits on the ellipse; sorting back-to-front keeps overlaps consistent.
        for x, y in sorted(note_positions(frame), key=lambda point: point[1]):
            canvas.alpha_composite(note, (round(x*SAMPLE_SCALE-note.width*0.4),
                                         round(y*SAMPLE_SCALE-note.height*0.8)))
        pictures.append(canvas.resize(SIZE, Image.Resampling.LANCZOS))
    return pictures
