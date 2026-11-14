"""Compile every generated DB00 art cell at its original generated resolution.

Local TTKTX02 specimens retain exact source/CLUT words, including partial words.
Generated masters and original disc data are read-only inputs.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
from ttk_anim import read_group, texture_page, vram_from_group
from texture_sample import build, validate

ROOT=Path(__file__).resolve().parents[3]
ART=ROOT/'recomp/analysis/level00-art-v2'
OUT=ROOT/'recomp/analysis/level00-realistic-complete'
SWIMWEAR=ART/'dancer-swimwear-fabric.png'
# DB00 HIE 13 owns MOD 377-389. The first two materials in the old
# alternate-costume sheets belong to other models and keep their existing art.
DANCER_MATERIALS={f'material-{i:04d}' for i in range(354,384)}


def dancer_tile(vram, reference, fabric):
    """Bake fabric detail over the native teal palette without moving UV edges."""
    native=Image.fromarray(texture_page(vram,reference['tpage'],reference['clut'])).crop(reference['box'])
    colors=np.asarray(native).astype(np.int16)
    red,green,blue,alpha=colors.transpose(2,0,1)
    mask=(alpha>0)&(green-red>=16)&(blue-red>=8)&(abs(green-blue)<=48)
    size=(native.width*8,native.height*8)
    base=np.asarray(native.convert('RGB').resize(size,Image.Resampling.LANCZOS),dtype=np.float32)
    weight=np.asarray(Image.fromarray(mask.astype(np.uint8)*255).resize(size,Image.Resampling.LANCZOS),
                      dtype=np.float32)/255.0
    detail=np.asarray(fabric.resize(size,Image.Resampling.LANCZOS),dtype=np.float32)
    detail=(detail-float(detail.mean()))/255.0
    result=base*(1.0+detail[:,:,None]*weight[:,:,None]*0.36)
    return Image.fromarray(np.rint(np.clip(result,0,255)).astype(np.uint8))


def main():
    review=json.loads((ART/'coverage.json').read_text(encoding='utf-8'))
    files=read_group(0)
    for name,meta in review['source_files'].items():
        assert hashlib.sha256(files[name]).hexdigest()==meta['sha256'],name
    vram=vram_from_group(files)
    OUT.mkdir(exist_ok=True,parents=True)
    fabric=None
    if SWIMWEAR.is_file():
        with Image.open(SWIMWEAR) as image:
            fabric=image.convert('L')
    fabric_digest=hashlib.sha256(SWIMWEAR.read_bytes()).hexdigest() if fabric is not None else None
    entries=[]
    for art in review['materials']:
        master=ART/art['art_master']
        digest=hashlib.sha256(master.read_bytes()).hexdigest()
        assert digest==review['atlases'][master.name]['sha256'],master.name
        with Image.open(master) as im:
            x,y=art['cell']%4,art['cell']//4
            w,h=im.size
            tile=im.convert('RGB').crop((round(x*w/4),round(y*h/4),round((x+1)*w/4),round((y+1)*h/4)))
        swimwear=fabric is not None and art['id'] in DANCER_MATERIALS
        for index,r in enumerate(art['references']):
            if swimwear:
                tile=dancer_tile(vram,r,fabric)
            rgb=tile.tobytes()
            tp,cl=r['tpage'],r['clut']
            u,v,ur,vr=r['box']
            m=dict(depth=(tp>>7)&3,page_x=(tp&15)*64,page_y=((tp>>4)&1)*256,
                   u=u,v=v,w=ur-u,h=vr-v,cx=(cl&63)*16,cy=cl>>6,iw=tile.width,ih=tile.height)
            ppw,pn=validate(m,2)
            x,y=m['page_x']+u//ppw,m['page_y']+v
            ww=(u%ppw+m['w']+ppw-1)//ppw
            words=vram[y:y+m['h'],x:x+ww].reshape(-1).tolist()
            palette=vram[m['cy'],m['cx']:m['cx']+pn].tolist()
            payload=build(m,words,palette,rgb,2)
            filename=(f'{art["id"]}-swim-{hashlib.sha256(payload).hexdigest()[:16]}.ttktx'
                      if swimwear else f'{art["id"]}-ref-{index:02d}.ttktx')
            (OUT/filename).write_bytes(payload)
            entries.append(dict(id=art['id'],file=filename,locator=m,world=r['world'],
                                alternate_costume=art['alternate_costume'] and not swimwear,
                                art_master=SWIMWEAR.name if swimwear else master.name,
                                cell=None if swimwear else art['cell'],art_input_sha256=fabric_digest if swimwear else digest,
                                dancer_swimwear=swimwear,
                                sha256=hashlib.sha256(payload).hexdigest()))
    assert {e['id'] for e in entries}=={a['id'] for a in review['materials']}
    assert len(entries)<=1024
    rgb_bytes=sum(e['locator']['iw']*e['locator']['ih']*3 for e in entries)
    assert rgb_bytes<=256*1024*1024
    temp=OUT/'pack.ttkpack.tmp'
    temp.write_bytes(('TTKPACK1\n'+''.join(e['file']+'\n' for e in entries)).encode('ascii'))
    temp.replace(OUT/'pack.ttkpack')
    report=dict(scope='All generated DB00 art; first-level gameplay, exact native source/CLUT required',
                materials=len(review['materials']),references=len(entries),entries=entries,
                alternate_costume_materials=len({e['id'] for e in entries if e['alternate_costume']}),
                dancer_swimwear_materials=len({e['id'] for e in entries if e['dancer_swimwear']}),
                rgb_bytes=rgb_bytes,enabled_by_default=False,
                note='Complete installation is not visual approval of every UV, animation or room. Menus without generated art remain original.')
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('materials','references','rgb_bytes',
                                          'alternate_costume_materials','dancer_swimwear_materials')}))


if __name__=='__main__':
    main()
