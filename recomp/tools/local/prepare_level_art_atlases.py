"""Pack connected UV reference regions for non-destructive AI art authoring."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from PIL import Image
from ttk_anim import read_group, vram_from_group, texture_page

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'recomp/analysis/level00-art-v2'


def overlaps(a,b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def main():
    manifest = json.loads((OUT/'inventory.json').read_text())
    groups = defaultdict(list)
    for a in manifest['assets']:
        groups[(a['tpage'],a['clut'])].append(a)
    vram = vram_from_group(read_group(0))
    regions = []
    for (tp,cl), assets in groups.items():
        clusters = []
        for a in assets:
            box = a['box'][:]
            members = [a]
            again = True
            while again:
                again = False
                for c in clusters[:]:
                    if overlaps(box,c['box']):
                        box = [min(box[0],c['box'][0]),min(box[1],c['box'][1]),max(box[2],c['box'][2]),max(box[3],c['box'][3])]
                        members += c['members']
                        clusters.remove(c)
                        again = True
            clusters.append(dict(box=box,members=members))
        for c in clusters:
            im = Image.fromarray(texture_page(vram,tp,cl)).crop(c['box'])
            # Only byte-identical images can share an art master.
            digest = hashlib.sha256(im.tobytes()+str(im.size).encode()).hexdigest()
            world = any(o['owner']=='world' for a in c['members'] for o in a['owners'])
            regions.append(dict(tpage=tp,clut=cl,box=c['box'],assets=[a['id'] for a in c['members']],
                                sha256=digest,world=world))
    dedup = {}
    for r in regions:
        if r['sha256'] not in dedup:
            dedup[r['sha256']] = dict(references=[],world=False)
        d = dedup[r['sha256']]
        d['references'].append(r)
        d['world'] |= r['world']
    items = sorted(dedup.values(),key=lambda x:not x['world'])
    (OUT/'references').mkdir(exist_ok=True)
    for i,item in enumerate(items):
        item['id'] = f'material-{i:04d}'
        r=item['references'][0]
        im=Image.fromarray(texture_page(vram,r['tpage'],r['clut'])).crop(r['box'])
        item['native_size']=list(im.size)
        item['reference']=f'references/{item["id"]}.png'
        im.save(OUT/item['reference'])
        item['atlas']=i//16
        item['cell']=i%16
        item['status']='pending-art'
    for batch in range((len(items)+15)//16):
        sheet=Image.new('RGB',(1024,1024),'#25252c')
        for j,item in enumerate(items[batch*16:(batch+1)*16]):
            im=Image.open(OUT/item['reference']).convert('RGBA').resize((256,256),Image.Resampling.NEAREST)
            sheet.paste(im,((j%4)*256,(j//4)*256),im)
        sheet.save(OUT/f'reference-atlas-{batch:02d}.png')
    result=dict(scope=manifest['scope'],materials=items,source_regions=len(regions),
                model_errors=manifest['model_errors'],decoder_repairs=manifest.get('decoder_repairs',[]),
                world_runs=manifest['world_runs'],source_files=manifest.get('source_files',{}),
                world_materials=sum(x['world'] for x in items))
    (OUT/'atlas-plan.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(materials=len(items),world_materials=result['world_materials'],atlases=(len(items)+15)//16)))


if __name__=='__main__':
    main()
