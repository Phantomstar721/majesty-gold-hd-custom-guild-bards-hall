"""Approved raster effects in private copies of native stock IMAG lifecycles."""
import copy
import hashlib
import json
import struct
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image, ImageChops, ImageOps
from cam_io import Entry, Section, name, read, write, section, u32

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'art/bard-world-effects-v2'
SONG_ART = ROOT / 'art/troub-song-effects-v1'
DANCER_ART = ROOT / 'art/dancer-effects-v1'
DANCER_KEYS = ('deflect', 'riposte', 'flourish')
SONG_KEYS = ('generic-cast', 'valor-target', 'march-target', 'satire-target', 'refrain-target')

def animation_source(key):
    if key in DANCER_KEYS:
        proof = json.loads((DANCER_ART/'review-status.json').read_text())
        assert proof['approved'] and proof['animation_family_approved']
        if key == 'deflect':
            sample = next(s for s in proof['samples'] if s['key'] == key)
            path = DANCER_ART/sample['source']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == sample['sha256']
            return path
        path = DANCER_ART/'animation-source'/f'{key}.png'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == proof['animation_sources'][key]['sha256']
        return path
    if key in SONG_KEYS:
        proof = json.loads((SONG_ART/'review-status.json').read_text())
        assert key in proof['approved_sample_keys'] and proof['animation_family_approved']
        if key == 'valor-target':
            sample = next(s for s in proof['samples'] if s['key'] == key)
            path = SONG_ART/sample['source']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == sample['sha256']
            return path
        path = SONG_ART/'animation-source'/f'{key}.png'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == proof['animation_sources'][key]['sha256']
        return path
    return ART/'animation-source'/f'{key}.png'
# Authored landmarks in each 627x627 source cell, in playback order. The
# generated sheet is not registered merely because it has equal-sized cells.
# Align before interpolation/quantization; brightening glows must not decide
# the origin. These are translations only, with one scale for all phases.
REGISTRATION = {
    'valor': ((336,211), (289,211), (336,156), (289,156)),  # central red jewel
    'countermelody': ((329,299), (299,298), (329,248), (299,245)), # note crossing
}
# key, private image, exact stock image prefix, visible box
SPECS = (
 ('valor','BFV1','HRB2',(18,20)), ('march','BFM1','DRA2',(22,14)),
 ('refrain','BFR1','QRa1',(20,20)), ('satire-r2','BFS1','PRB2',(18,20)),
 ('reverberation','BFN1','PRB2',(26,24)), ('countermelody','BFC1','HRB2',(20,20)),
 ('roused','BFO1','HRB2',(18,20)), ('encore','BFE1','HRB2',(20,20)),
 ('song-cast','BFX1','HRB1',(32,28)), ('resonant-burst','BFX2','SRa1',(72,44)),
 ('countermelody-cast','BFX3','WRa1',(44,40)), ('echo-impact','BFX4','WRa1',(24,22)),
 ('dancer-finale','BFX5','HRB1',(52,44)), ('arcane-note','BFN2','WPa2',(25,25)),
 ('finale-ready','BFT1','HRB2',(20,20)),
 ('generic-cast','BFX6','HRB1',(28,28)),
 ('valor-target','BTV1','HRa1',(36,48)), ('march-target','BTM1','HRa1',(36,48)),
 ('satire-target','BTS1','HRa1',(36,48)), ('refrain-target','BTR1','HRa1',(36,48)),
 ('deflect','BDF1','HRB1',(28,24)), ('riposte','BRP1','HRB1',(28,24)),
 ('flourish','BFL1','HRB1',(40,32)),
)
OVERLAYS = dict(zip(('Bards_Valor_Icon','Bards_March_Icon','Bards_Refrain_Icon',
 'Bards_Satire_Icon','Bards_Reverberation_Icon','Bards_Countermelody_Icon',
 'Bards_Roused_Icon','Bards_Encore_Icon'),(s[1] for s in SPECS[:8])))
OVERLAYS['Bards_Finale_Ready_Icon'] = 'BFT1'
ONESHOTS = (
 ('Bards_Song_Flash','BFX1','blessing_effector'),
 ('Bards_Burst_Flash','BFX2','sun_scorch_effector1'),
 ('Bards_Counter_Flash','BFX3','energy_blast_effector'),
 ('Bards_Echo_Flash','BFX4','energy_blast_effector'),
 ('Bards_Finale_Flash','BFX5','blessing_effector'),
 ('Bards_Deflect_Flash','BDF1','blessing_effector'),
 ('Bards_Riposte_Flash','BRP1','blessing_effector'),
 ('Bards_Flourish_Flash','BFL1','blessing_effector'),
 ('Bards_Valor_Flash','BTV1','healer_healing_effector'),
 ('Bards_March_Flash','BTM1','healer_healing_effector'),
 ('Bards_Satire_Flash','BTS1','healer_healing_effector'),
 ('Bards_Refrain_Flash','BTR1','healer_healing_effector'),
)

def bind_descriptions(output, stock_overlays):
    for d in output:
        prefix = OVERLAYS.get(d.get('Name'))
        if d.get('Name') == 'Bards_Arcane_Note_Missile': prefix = 'BFN2'
        if prefix: d.find('./Engine/ImageIDBase').set('value',prefix)
    for label, prefix, original in ONESHOTS:
        d = copy.deepcopy(stock_overlays.find(f'.//Description[@Name="{original}"]'))
        d.attrib.update(ID=prefix,Name=label,Description=label.replace('_',' '))
        d.find('./Engine/ImageIDBase').set('value', prefix)
        d.find('./Engine/DefaultSound').set('value','0')
        output.append(d)

    from bards_crescendo_art import description as crescendo_description
    output.append(crescendo_description(stock_overlays))

def patch_hero_cast(blob, hero_id, authority, tiles):
    """Haunt's stock secondary-cast replacement; preserve body and recovery."""
    # Dancer effects belong to each action/reaction callback, not every Cast.
    result=bytearray(blob)
    prefix={'BDT1':'BFX6','BDS1':'BFX1','BDD1':'BFX5'}[hero_id]
    phases=(0,7,14,21,27)
    lookup={e.name.rstrip(b'\0'):i for i,e in enumerate(tiles)}
    # Notes TILEs include a raised performance hotspot; compensate on Cast.
    y=-12 if hero_id == 'BDS1' else -40
    for record in authority['package_contract']['cast_secondary_stream']['occurrences']:
        if hero_id == 'BDD1':
            offset=record['reference_offset'];old=u32(result,offset)
            struct.pack_into('<I',result,offset,(old&0xffff0000)|lookup[b'BDZ00000'])
            continue
        if record['frame']>=5: continue
        offset=record['reference_offset'];old=u32(result,offset)
        index=lookup[f'{prefix}{phases[record["frame"]]:04d}'.encode()]
        x=-18 if record['slot'] in (5,6,7) else 18
        struct.pack_into('<hh',result,record['metadata_offset'],x,y)
        struct.pack_into('<I',result,offset,(old&0xffff0000)|index)
    return bytes(result)

def streams(blob):
    """Retail effects have ordinary or 24-byte padded direction headers."""
    sets = [struct.unpack_from('<II',blob,24+i*8) for i in range(u32(blob,20))]
    for i,(sid,start) in enumerate(sets):
        end = sets[i+1][1] if i+1<len(sets) else len(blob)
        count = u32(blob,start)
        assert 0 < count <= 32
        pointers = [start+u32(blob,start+64+d*4) for d in range(count)]
        for d,pointer in enumerate(pointers):
            stop = pointers[d+1] if d+1<count else end
            field = pointer+4
            if u32(blob,field)==0: field += 24
            packed = u32(blob,field)
            frames, layers = packed>>16, packed&65535
            first = stop-frames*layers*8
            assert frames>0 and 0<layers<=8 and first-field-4 in (0,8,16), (sid,first,field)
            for layer in range(layers):
                yield sid,d,layer,list(range(first+layer*frames*8+4,first+(layer+1)*frames*8,8))

def strip_frames(key,box):
    if key in ('valor-target', 'deflect'):
        # Keep the approved aura's exact silhouette and alpha. The generated
        # four-pose sheet thickened its rim; opacity is the only animated value.
        im = Image.open(animation_source(key)).convert('RGBA')
        bounds = im.getchannel('A').point(lambda v:255 if v>=24 else 0).getbbox()
        small = im.crop(bounds)
        small.thumbnail(box, Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA',box)
        canvas.alpha_composite(small,((box[0]-small.width)//2,(box[1]-small.height)//2))
        frames=[]
        for opacity in (0.45, 1.0, 0.6, 0.08):
            frame=canvas.copy()
            frame.putalpha(canvas.getchannel('A').point(lambda v:round(v*opacity)))
            frames.append(frame)
        return frames
    if key == 'finale-ready':
        root = ROOT / 'art/finale-target-marker-v1'
        proof = json.loads((root/'review-status.json').read_text())
        path = root/'B-20px.png'
        assert proof['runtime_custom_art_approved'] and proof['selected_option'] == 'B'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == proof['runtime_sha256']
        small = Image.open(path).convert('RGBA')
        canvas = Image.new('RGBA', box)
        canvas.alpha_composite(small, ((box[0]-small.width)//2, (box[1]-small.height)//2))
        return [canvas.copy() for _ in range(4)]
    path=animation_source(key)
    im=Image.open(path).convert('RGBA')
    cells=[]
    for y in range(2):
        for x in range(2):
            c=im.crop((x*im.width//2,y*im.height//2,(x+1)*im.width//2,(y+1)*im.height//2))
            if c.getextrema()[3]==(255,255):
                r,g,b,_=c.split()
                a=ImageChops.lighter(ImageChops.lighter(r,g),b)
                c.putalpha(a.point(lambda v:0 if v<=4 else min(255,round((v-4)*1.45))))
            cells.append(c)
    if key in DANCER_KEYS:
        # Register equal-sized source cells before the common crop/scale.
        # These stationary flashes have a fixed center, not traveling particles.
        aligned=[]
        for c in cells:
            b=c.getchannel('A').point(lambda v:255 if v>=24 else 0).getbbox()
            canvas=Image.new('RGBA',c.size)
            canvas.alpha_composite(c,(round((c.width-b[0]-b[2])/2),round((c.height-b[1]-b[3])/2)))
            aligned.append(canvas)
        cells=aligned
    if key in REGISTRATION:
        assert im.size == (1254,1254), 'Registered source dimensions changed'
        anchors=REGISTRATION[key]
        aligned=[]
        for c,anchor in zip(cells,anchors):
            canvas=Image.new('RGBA',c.size)
            canvas.alpha_composite(c,(anchors[0][0]-anchor[0],anchors[0][1]-anchor[1]))
            aligned.append(canvas)
        cells=aligned
    # One shared crop/scale for the entire family; never fit each frame.
    bounds=[c.getchannel('A').point(lambda v:255 if v>=24 else 0).getbbox() for c in cells]
    assert all(bounds), key
    union=(min(b[0] for b in bounds),min(b[1] for b in bounds),max(b[2] for b in bounds),max(b[3] for b in bounds))
    scale=min(box[0]/(union[2]-union[0]),box[1]/(union[3]-union[1]))
    size=(max(1,round((union[2]-union[0])*scale)),max(1,round((union[3]-union[1])*scale)))
    result=[]
    for c in cells:
        small=c.crop(union).resize(size,Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',box)
        canvas.alpha_composite(small,((box[0]-size[0])//2,(box[1]-size[1])//2))
        result.append(canvas)
    if key in DANCER_KEYS:
        for frame,opacity in zip(result,(0.45,1.0,0.6,0.08)):
            frame.putalpha(frame.getchannel('A').point(lambda v:round(v*opacity)))
    return result

def indexed(pictures, *, soft_glow=False):
    w,h=pictures[0].size
    atlas=Image.new('RGB',(w*len(pictures),h))
    rgb_pictures=[]
    for i,p in enumerate(pictures):
        rgb = p.convert('RGB')
        if soft_glow:
            # Native TILE uses binary coverage. Preserve the approved soft
            # glow as dim palette colors instead of opaque saturated bands.
            rgb = Image.new('RGB',p.size)
            rgb.paste(p.convert('RGB'),(0,0),p.getchannel('A'))
        rgb_pictures.append(rgb)
        atlas.paste(rgb,(i*w,0))
    quant=atlas.quantize(colors=246,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    colors=[(0,0,0)]+list(zip(*[iter(quant.getpalette()[:738])]*3))
    colors += [(0,0,0)]*(256-len(colors))
    palette=struct.pack('<4H',0,256,0,0)+bytes(c for rgb in colors for c in (*rgb,0))
    planes=[]
    for p,rgb in zip(pictures,rgb_pictures):
        q=rgb.quantize(palette=quant,dither=Image.Dither.NONE)
        planes.append(bytes(v+1 if a>=80 else 0 for v,a in zip(q.tobytes(),p.getchannel('A').tobytes())))
    return planes,palette,colors

def tile(plane,size,palette,hotspot):
    # Same TILE-v3 exclusive-run encoder as the registered Chronicles pipeline.
    w,h=size
    header=bytearray(26)
    struct.pack_into('<5HhhH',header,0,3,h,w,0,32,*hotspot,8)
    struct.pack_into('<HI',header,20,0,palette)
    rows,offsets=bytearray(),bytearray()
    for y in range(h):
        offsets+=struct.pack('<I',4*h+len(rows));row=plane[y*w:(y+1)*w];runs=[];x=0
        while x<w:
            if not row[x]: x+=1;continue
            start=x
            while x<w and row[x]: x+=1
            runs.append((x,row[start:x]))
        if not runs:runs=[(0,b'')]
        for i,(end,pixels) in enumerate(runs):rows+=struct.pack('<HH',end,len(pixels)|(0x8000 if i==len(runs)-1 else 0))+pixels
    return bytes(header+offsets+rows)

def append_art(stock,tiles,palettes):
    images=[];evidence=[]
    preview=ART/'runtime-preview';preview.mkdir(exist_ok=True)
    for index,(key,prefix,original,box) in enumerate(SPECS):
        source=next(e for e in section(stock,b'IMAG').entries if e.name.startswith(original.encode()))
        blob=bytearray(source.data);cells=strip_frames(key,box);loop=index<8 or key=='arcane-note'
        pindex=len(palettes);rendered=[];patches=[]
        # Stock channels, directions, phase words, ordering, flags, and timing
        # remain byte-for-byte intact. Only low16 TILE references are private.
        for sid,direction,layer,refs in streams(source.data):
            for f,offset in enumerate(refs):
                word=u32(blob,offset);flags=word>>16
                phase=f*4/len(refs) if loop else f*3/max(1,len(refs)-1)
                left=min(3,int(phase));right=(left+1)%4 if loop else min(3,left+1)
                picture=Image.blend(cells[left],cells[right],phase-left)
                # Store one complete visible effect, not repeated layer copies.
                if layer>0:picture=Image.new('RGBA',box)
                hotspot=(box[0]//2,box[1]//2 + (28 if key=='song-cast' else 0))
                if flags&0x2000:
                    picture=ImageOps.mirror(picture);hotspot=(box[0]-hotspot[0],hotspot[1])
                rendered.append(picture);patches.append((offset,word,hotspot))
        planes,palette,colors=indexed(rendered,soft_glow=key=='valor-target' or key in DANCER_KEYS);palettes.append(Entry(name((prefix+'Palette').encode()),palette))
        for n,((offset,word,hotspot),plane) in enumerate(zip(patches,planes)):
            assert len(tiles)<65536
            struct.pack_into('<I',blob,offset,(word&0xffff0000)|len(tiles))
            tiles.append(Entry(name(f'{prefix}{n:04d}'.encode()),tile(plane,box,pindex,hotspot)))
        images.append(Entry(name((prefix+key[:16]).encode()),bytes(blob)))
        # Native palette/alpha preview, not the unquantized source art.
        native=[]
        for plane in planes[:len(next(streams(source.data))[3])]:
            p=Image.new('RGBA',box);p.putdata([(*colors[v],255 if v else 0) for v in plane]);native.append(p)
        native[0].save(preview/f'{key}.png')
        frames=[]
        for p in native:
            bg=Image.new('RGB',(box[0]*4,box[1]*4),(35,44,42));q=p.resize(bg.size,Image.Resampling.NEAREST);bg.paste(q,(0,0),q);frames.append(bg)
        frames[0].save(preview/f'{key}.gif',save_all=True,append_images=frames[1:],duration=100,loop=0)
        source_path = ROOT/'art/finale-target-marker-v1/B-20px.png' if key == 'finale-ready' else animation_source(key)
        evidence.append(dict(key=key,image=prefix,stock=source.name.rstrip(b'\0').decode(),stock_sha256=hashlib.sha256(source.data).hexdigest(),frames=len(patches),size=box,registration_anchors=REGISTRATION.get(key),source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest()))
    # Transparent replacement for Dancer's shared Cast secondary layer; retain
    # all native body frames, layer counts, flags, timing and recovery frames.
    tiles.append(Entry(name(b'BDZ00000'),tile(bytes(1),(1,1),0,(0,0))))
    from bards_crescendo_art import append_art as append_crescendo
    crescendo, proof = append_crescendo(stock, tiles, palettes)
    images.append(crescendo); evidence.append(proof)
    (ART/'runtime-manifest.json').write_text(json.dumps(evidence,indent=2)+'\n')
    return images,evidence

def validate(game,package):
    stock=read(game/'Data/maindata.cam');actual=read(package/'Data/bards_maindata.cam')
    tiles=section(actual,b'TILE').entries;stock_tiles=section(stock,b'TILE').entries
    assert [(e.name,e.data) for e in tiles[:len(stock_tiles)]]==[(e.name,b'') for e in stock_tiles]
    from bards_building_art import decode_indices
    for key,prefix,original,box in SPECS:
        source=next(e.data for e in section(stock,b'IMAG').entries if e.name.startswith(original.encode()))
        result=next(e.data for e in section(actual,b'IMAG').entries if e.name.startswith(prefix.encode()))
        restored=bytearray(result)
        for _,_,_,refs in streams(source):
            for offset in refs:
                assert u32(result,offset)>>16==u32(source,offset)>>16
                data=tiles[u32(result,offset)&65535].data
                decode_indices(data,size=box,hotspot=struct.unpack_from('<hh',data,10))
                restored[offset:offset+4]=source[offset:offset+4]
        assert restored==source, 'Changed stock playback: '+key
