"""Compile a bounded first-level scenery pilot from the local art review.

All specimens contain owned source words and remain under ignored analysis/.
The renderer must independently compare authoritative GL source/CLUT content.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image
from ttk_anim import read_group, vram_from_group
from texture_sample import build, validate

ROOT=Path(__file__).resolve().parents[3]
ART=ROOT/'recomp/analysis/level00-art-v2'
OUT=ROOT/'recomp/analysis/level00-realistic-2x'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preset',choices=('pilot','hd'),default='pilot')
    args=parser.parse_args()
    hd=args.preset=='hd'
    out=ROOT/'recomp/analysis/level00-realistic-hd' if hd else OUT
    review=json.loads((ART/'coverage.json').read_text(encoding='utf-8'))
    files=read_group(0)
    for name,meta in review['source_files'].items():
        assert hashlib.sha256(files[name]).hexdigest()==meta['sha256'],name
    vram=vram_from_group(files)
    items=sorted(review['materials'],key=lambda a:(a['id'] not in ('material-0034','material-0035'),a['id']))
    entries=[]
    out.mkdir(parents=True,exist_ok=True)
    for a in items:
        if not a['world'] or a['alternate_costume']:
            continue
        # The original pilot limits size. HD also admits larger packed scenery
        # regions; both modes retain native source/CLUT and cutout semantics.
        if not hd and (max(a['native_size'])>64 or min(a['native_size'])<16):
            continue
        with Image.open(ART/a['reference']) as source:
            if source.mode=='RGBA' and source.getchannel('A').getextrema()!=(255,255):
                continue
        r=next((r for r in a['references'] if r['world']),None)
        if not r:
            continue
        tp,cl=r['tpage'],r['clut'];u,v,ur,vr=r['box'];depth=(tp>>7)&3
        m=dict(depth=depth,page_x=(tp&15)*64,page_y=((tp>>4)&1)*256,
               u=u,v=v,w=ur-u,h=vr-v,cx=(cl&63)*16,cy=cl>>6,iw=(ur-u)*2,ih=(vr-v)*2)
        try:
            ppw,pn=validate(m)
        except ValueError:
            continue
        x,y=m['page_x']+u//ppw,m['page_y']+v
        words=vram[y:y+m['h'],x:x+m['w']//ppw].reshape(-1).tolist()
        palette=vram[m['cy'],m['cx']:m['cx']+pn].tolist()
        if hd:
            # Compile the selected original generated cell, not its 2X export.
            # Uniform integer enlargement is the specimen wire contract. Round
            # up the longest edge to retain the master's available definition.
            image=ART/a['art_master']
            assert hashlib.sha256(image.read_bytes()).hexdigest()==review['atlases'][image.name]['sha256']
            with Image.open(image) as master:
                x,y=a['cell']%4,a['cell']//4
                tw,th=master.size
                im=master.convert('RGB').crop((round(x*tw/4),round(y*th/4),round((x+1)*tw/4),round((y+1)*th/4)))
            scale=max(1,math.ceil(max(im.size)/max(m['w'],m['h'])))
            m.update(iw=m['w']*scale,ih=m['h']*scale)
            validate(m)
            im=im.resize((m['iw'],m['ih']),Image.Resampling.LANCZOS)
            payload=build(m,words,palette,im.tobytes())
        else:
            image=ART/a['diffuse_2x']
            assert hashlib.sha256(image.read_bytes()).hexdigest()==a['sha256_2x']
            with Image.open(image) as im:
                assert im.size==(m['iw'],m['ih'])
                payload=build(m,words,palette,im.convert('RGB').tobytes())
        name=a['id']+'.ttktx'
        (out/name).write_bytes(payload)
        entries.append(dict(id=a['id'],file=name,locator=m,sha256=hashlib.sha256(payload).hexdigest(),
                            art_master=a['art_master'],cell=a['cell'],art_input_sha256=hashlib.sha256(image.read_bytes()).hexdigest()))
        if len(entries)==(64 if hd else 16):
            break
    assert len(entries)==(64 if hd else 16) and {'material-0034','material-0035'}<={e['id'] for e in entries}
    temporary=out/'pack.ttkpack.tmp'
    temporary.write_bytes(('TTKPACK1\n'+''.join(e['file']+'\n' for e in entries)).encode('ascii'))
    temporary.replace(out/'pack.ttkpack')
    report=dict(scope='Expanded first-level scenery HD, 64 regions from generated masters; not full phase replacement' if hd else 'First-level scenery lot 1, optional 2X; not full phase replacement',
                entries=entries,rgb_bytes=sum(e['locator']['iw']*e['locator']['ih']*3 for e in entries),
                enabled_by_default=False,source_review='recomp/analysis/level00-art-v2/coverage.json')
    (out/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(entries=len(entries),rgb_bytes=report['rgb_bytes'],output=out.relative_to(ROOT).as_posix())))


if __name__=='__main__':
    main()
