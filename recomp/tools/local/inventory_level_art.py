"""Read-only art inventory from owned DB00. Outputs remain local under analysis."""
import json
import argparse
import hashlib
import struct
from pathlib import Path
from PIL import Image, ImageDraw
from ttk_anim import read_group, vram_from_group, texture_page, parse_model

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'recomp/analysis/level00-art-v2'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-sheets', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    files = read_group(0)
    vram = vram_from_group(files)
    level = files['LEVEL00']
    # A world texture record is four UV pairs, CLUT at +2 and tpage at +6.
    def record(at):
        b = level[at:at+12]
        if len(b) != 12:
            return None
        clut, tpage = struct.unpack_from('<H', b, 2)[0], struct.unpack_from('<H', b, 6)[0]
        if tpage & ~0x1ff or not 8 <= (tpage & 15) <= 14 or ((tpage >> 7) & 3) > 1:
            return None
        if (clut & 63)*16 < 512 or clut >> 6 >= 512:
            return None
        uv = [(b[i], b[i+1]) for i in (0, 4, 8, 10)]
        return dict(tpage=tpage, clut=clut, uv=uv, offset=at, owner='world')
    runs = []
    for residue in range(12):
        run = []
        for at in range(residue, len(level)-11, 12):
            r = record(at)
            if r:
                run.append(r)
            else:
                if len(run) >= 8:
                    runs.append(run)
                run = []
        if len(run) >= 8:
            runs.append(run)
    runs.sort(key=len, reverse=True)
    print('world candidate runs', [(len(r), r[0]['offset'], r[-1]['offset']) for r in runs[:8]])
    # Authenticate the trailing table against its preceding count and file end.
    assert len(runs) == 1
    table_count = struct.unpack_from('<I',level,runs[0][0]['offset']-4)[0]
    assert table_count == len(runs[0])
    assert runs[0][-1]['offset']+12 == len(level)
    records = [r for run in runs for r in run]
    models, errors, repairs = 0, [], []
    for index in range(2048):
        if struct.unpack_from('<i', files['MOD'], 4*index)[0] == -1:
            continue
        try:
            model = parse_model(files['MOD'], index)
        except (struct.error, KeyError, IndexError) as exc:
            errors.append(dict(model=index, error=type(exc).__name__))
            continue
        models += 1
        records += [dict(**p, owner='model', model=index) for p in model['prims'] if 'uv' in p]
    # The native object renderer reads byte +6, not a halfword. Retry after
    # existing entries to preserve previously assigned art IDs. Only a private
    # RAM copy of the source bytes is adjusted for the legacy decoder.
    for error in errors[:]:
        index = error['model']
        data = bytearray(files['MOD'])
        offset = struct.unpack_from('<i',data,index*4)[0]+0x2000
        if data[offset+7] == 0:
            continue
        data[offset+7] = 0
        model = parse_model(data,index)
        records += [dict(**p, owner='model', model=index) for p in model['prims'] if 'uv' in p]
        models += 1
        repairs.append(dict(model=index,reason='vertex count at +6 is u8; header byte +7 is flags'))
        errors.remove(error)
    unique = {}
    for r in records:
        u, vs = zip(*r['uv'])
        box = (min(u), min(vs), max(u)+1, max(vs)+1)
        key = (r['tpage'], r['clut'], box)
        if key not in unique:
            unique[key] = dict(tpage=r['tpage'], clut=r['clut'], box=box, owners=[], uses=0)
        a = unique[key]
        a['uses'] += 1
        owner = {k:r[k] for k in ('owner','model','offset') if k in r}
        if owner not in a['owners']:
            a['owners'].append(owner)
    assets = []
    for i, a in enumerate(unique.values()):
        try:
            page = texture_page(vram, a['tpage'], a['clut'])
            im = Image.fromarray(page).crop(a['box'])
        except (ValueError, IndexError):
            continue
        name = f'tex-{i:04d}'
        a.update(id=name, source=f'sources/{name}.png', status='source-only')
        (OUT / 'sources').mkdir(exist_ok=True)
        im.save(OUT / a['source'])
        assets.append(a)
    # Technical contact sheets, one reference tile per cell, no creative edits.
    for batch in range(0 if args.skip_sheets else (len(assets)+63)//64):
        sheet = Image.new('RGB', (1024,1024), '#34343c')
        d = ImageDraw.Draw(sheet)
        for j,a in enumerate(assets[batch*64:(batch+1)*64]):
            im = Image.open(OUT/a['source']).convert('RGBA')
            im.thumbnail((120,104), Image.Resampling.NEAREST)
            x,y=(j%8)*128,(j//8)*128
            sheet.paste(im,(x+(128-im.width)//2,y+4),im)
            d.text((x+4,y+110),a['id'],fill='white')
        sheet.save(OUT/f'inventory-{batch:02d}.png')
    manifest = dict(scope='Complete DB00 trailing world texture table (count and file boundary checked) and all MOD texture references; per-room usage not traced',
                    asset_group='DB00',
                    source_files={k:dict(bytes=len(files[k]),sha256=hashlib.sha256(files[k]).hexdigest())
                                  for k in ('LEVEL00','MOD','A.RAW','B.RAW')},
                    world_runs=[dict(count=len(r),start=r[0]['offset'],end=r[-1]['offset']+12) for r in runs],
                    models=models,model_errors=errors,decoder_repairs=repairs,assets=assets)
    (OUT/'inventory.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(dict(assets=len(assets),models=models,model_errors=errors, sheets=(len(assets)+63)//64)))


if __name__ == '__main__':
    main()
