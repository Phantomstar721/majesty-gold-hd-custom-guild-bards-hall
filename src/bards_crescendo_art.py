"""Approved Crescendo A, baked into stock overhead Blessing playback."""
import copy
import hashlib
import json
import math
import struct
from pathlib import Path
from PIL import Image, ImageOps
from cam_io import Entry, name, section, u32

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT/'art/crescendo-stun-v1'
PREFIX = 'BCS1'
SIZE = (32, 22)
CENTER = (16, 11)
HOTSPOT = (16, 15)  # Four pixels above the native overhead status anchor.


def description(overlays):
    # Stock Blessing owns animated overhead placement and status stacking.
    # As in Alchemist's private restraint, the timed visible overlay owns the
    # stock paralysis end callback; it is not a second independently timed stun.
    d = copy.deepcopy(overlays.find('.//Description[@Name="blessing_icon"]'))
    d.attrib.update(ID=PREFIX, Name='Bards_Crescendo_Icon', Description='Crescendo')
    d.find('./Engine/ImageIDBase').set('value', PREFIX)
    d.find('./Engine/Script').set('GPLFunction', 'Paralytic_Gaze_End')
    return d


def frames(count):
    proof = json.loads((ART/'review-status.json').read_text())
    source = ART/'orbit-components.png'
    assert proof['runtime_custom_art_approved'] and proof['animation_family_approved']
    assert proof['selected_option'] == 'A'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == proof['component_sha256']
    im = Image.open(source).convert('RGBA')
    # One fixed ring and one upright star. No independently generated frames
    # or moving bounding-box origins. Follow the registered Chronicles method.
    cut = round(im.height * .61)
    def component(box, size):
        p = im.crop(box)
        bounds = p.getchannel('A').point(lambda v:255 if v>=24 else 0).getbbox()
        return p.crop(bounds).resize(tuple(v*8 for v in size), Image.Resampling.LANCZOS)
    ring = component((0,0,im.width,cut),(28,12))
    star = component((0,cut,im.width,im.height),(6,8))
    result=[]
    for frame in range(count):
        canvas=Image.new('RGBA',(SIZE[0]*8,SIZE[1]*8))
        canvas.alpha_composite(ring,(CENTER[0]*8-ring.width//2,CENTER[1]*8-ring.height//2))
        # One third-turn per loop is seamless with three identical stars.
        phase=frame*math.tau/(3*count)
        positions=[(CENTER[0]+11*math.cos(phase+i*math.tau/3),
                    CENTER[1]+5*math.sin(phase+i*math.tau/3)) for i in range(3)]
        for x,y in sorted(positions,key=lambda p:p[1]):
            canvas.alpha_composite(star,(round(x*8-star.width/2),round(y*8-star.height/2)))
        result.append(canvas.resize(SIZE,Image.Resampling.LANCZOS))
    return result


def append_art(stock, tiles, palettes):
    from bards_world_effects import streams, indexed, tile
    source=next(e for e in section(stock,b'IMAG').entries if e.name.startswith(b'HRB2'))
    blob=bytearray(source.data)
    pictures=[];patches=[]
    for sid,direction,layer,refs in streams(source.data):
        poses=frames(len(refs))
        for offset,picture in zip(refs,poses):
            word=u32(blob,offset)
            if layer: picture=Image.new('RGBA',SIZE)
            if word>>16 & 0x2000: picture=ImageOps.mirror(picture)
            pictures.append(picture);patches.append((offset,word))
    planes,palette,colors=indexed(pictures,soft_glow=True)
    pindex=len(palettes)
    palettes.append(Entry(name(b'BCS1Palette'),palette))
    for i,((offset,word),plane) in enumerate(zip(patches,planes)):
        assert len(tiles)<65536
        struct.pack_into('<I',blob,offset,(word&0xffff0000)|len(tiles))
        tiles.append(Entry(name(f'BCS1{i:04d}'.encode()),tile(plane,SIZE,pindex,HOTSPOT)))
    # Preview exactly the indexed runtime pixels, not the high-resolution kit.
    preview=[]
    for plane in planes:
        p=Image.new('RGBA',SIZE)
        p.putdata([(*colors[v],255 if v else 0) for v in plane])
        preview.append(p)
    preview[0].save(ART/'runtime-native.png')
    for scale in (1,4):
        display=[]
        for p in preview:
            bg=Image.new('RGB',(SIZE[0]*scale,SIZE[1]*scale),'#29352e')
            q=p.resize(bg.size,Image.Resampling.NEAREST);bg.paste(q,(0,0),q);display.append(bg)
        display[0].save(ART/f'runtime-{scale}x.gif',save_all=True,append_images=display[1:],duration=100,loop=0)
    restored=bytearray(blob)
    for offset,word in patches:struct.pack_into('<I',restored,offset,word)
    assert restored==source.data
    evidence=dict(key='crescendo',image=PREFIX,stock=source.name.rstrip(b'\0').decode(),
                  frames=len(planes),size=SIZE,hotspot=HOTSPOT,overhead_lift=4,
                  source_sha256=proof_hash(),native_playback_unchanged=True)
    (ART/'runtime-manifest.json').write_text(json.dumps(evidence,indent=2)+'\n')
    return Entry(name(b'BCS1Crescendo'),bytes(blob)),evidence


def proof_hash():
    return hashlib.sha256((ART/'orbit-components.png').read_bytes()).hexdigest()
