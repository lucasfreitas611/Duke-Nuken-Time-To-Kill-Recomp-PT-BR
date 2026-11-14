"""Build a local level pack from available generated art and exact VRAM identities."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image
from build_complete_texture_pack import DANCER_MATERIALS, SWIMWEAR
from disc_lab import Disc
from inventory_campaign_art import GROUP, OUT, RECOMP
from texture_sample import build, validate
from ttk_anim import DISC_PATH, vram_from_group


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank', type=int, choices=range(1, 32))
    args = parser.parse_args()
    bank = args.bank
    disc = Disc(DISC_PATH)
    try:
        source = {}
        for entry in disc.files():
            match = GROUP.fullmatch(entry['path'])
            if not match or int(match[1]) != bank:
                continue
            name = match[2].removeprefix(f'DB{bank:02d}')
            if name in ('A.RAW', 'B.RAW'):
                source[name] = disc.read(entry['lba'], entry['size'])
    finally:
        disc.close()
    vram = vram_from_group(source)
    catalog = json.loads((OUT/'inventory.json').read_text(encoding='utf-8'))
    has_swimwear = SWIMWEAR.is_file()
    generated = OUT/'generated.json'
    additions = json.loads(generated.read_text(encoding='utf-8')) if generated.is_file() else {}
    originals = RECOMP/'analysis/level00-art-v2'
    out = OUT/'packs'/f'{bank:02d}'
    out.mkdir(exist_ok=True, parents=True)
    entries = []
    missing = []
    for material in catalog['materials']:
        refs = [r for r in material['references'] if r['bank'] == bank]
        if not refs:
            continue
        added = additions.get(material['sha256'])
        existing = material['existing_art']
        # The old sheets painted over UVs with a jumpsuit. Do not propagate
        # those obsolete cells to other banks through exact source matches.
        if has_swimwear and existing and existing['id'] in DANCER_MATERIALS:
            existing = None
        artwork = added or existing
        if not artwork:
            missing.append(material['sha256'])
            continue
        base = OUT if added else originals
        with Image.open(base/artwork['master']) as master:
            x, y = artwork['cell'] % 4, artwork['cell'] // 4
            width, height = master.size
            tile = master.convert('RGB').crop((round(x*width/4), round(y*height/4),
                                               round((x+1)*width/4), round((y+1)*height/4)))
        rgb = tile.tobytes()
        for ref in refs:
            u, v, right, bottom = ref['box']
            page, clut = ref['page'], ref['clut']
            loc = dict(depth=(page >> 7) & 3, page_x=(page & 15)*64,
                       page_y=((page >> 4) & 1)*256, u=u, v=v, w=right-u, h=bottom-v,
                       cx=(clut & 63)*16, cy=clut >> 6, iw=tile.width, ih=tile.height)
            ppw, colors = validate(loc, 2)
            x, y = loc['page_x'] + u//ppw, loc['page_y'] + v
            words = (u%ppw + loc['w'] + ppw - 1)//ppw
            texels = vram[y:y+loc['h'], x:x+words].reshape(-1).tolist()
            palette = vram[loc['cy'], loc['cx']:loc['cx']+colors].tolist()
            payload = build(loc, texels, palette, rgb, 2)
            digest = hashlib.sha256(payload).hexdigest()
            name = f'{digest}.ttktx'
            if not (out/name).is_file():
                (out/name).write_bytes(payload)
            entries.append(dict(file=name, material=material['sha256'], new_art=bool(added),
                                rgb_bytes=len(rgb), owners=ref['owners']))
    if len(entries) > 1024 or sum(e['rgb_bytes'] for e in entries) > 256*1024*1024:
        raise SystemExit('Pack exceeds the renderer budget')
    if not entries:
        raise SystemExit(f'Bank {bank} has no matched generated art')
    temp = out/'pack.ttkpack.tmp'
    temp.write_bytes(('TTKPACK1\n'+''.join(e['file']+'\n' for e in entries)).encode('ascii'))
    temp.replace(out/'pack.ttkpack')
    report = dict(bank=bank, entries=entries, materials_pending=missing)
    (out/'manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(bank=bank, references=len(entries), new_references=sum(e['new_art'] for e in entries),
                          pending_materials=len(missing))))


if __name__ == '__main__':
    main()
