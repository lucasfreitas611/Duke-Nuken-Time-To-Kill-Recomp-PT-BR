"""Catalog the owned disc's world and MOD texture regions across all banks."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct

from PIL import Image
from disc_lab import Disc
from ttk_anim import DISC_PATH, parse_hierarchies, parse_model, texture_page, vram_from_group
from prepare_level_art_atlases import overlaps
from texture_sample import validate

RECOMP = Path(__file__).resolve().parents[2]
OUT = RECOMP / 'analysis/campaign-art'
GROUP = re.compile(r'^/D\d/DB(\d{2})/([^;]+);\d+$')
RECORD = struct.Struct('<BBHBBHBBBB')
# Verified byte-for-byte against the live renderer's table in each challenge.
# The geometry comes from the linked bank, while the challenge uploads its own VRAM.
CHALLENGE_WORLDS = {21: 19, 22: 15, 23: 16, 24: 17, 25: 20, 26: 18}


def world_table(data):
    """Require the count, the file boundary and every record's VRAM fields."""
    candidates = []
    for start in range(len(data) % 12, len(data) - 11, 12):
        if start < 4:
            continue
        count = (len(data) - start) // 12
        if struct.unpack_from('<I', data, start - 4)[0] != count:
            continue
        records = list(RECORD.iter_unpack(data[start:]))
        if all(world_record(r) or (r[5], r[2]) in ((0x200, 0), (0, 0xffff)) for r in records):
            candidates.append((start, records))
    if not candidates:
        raise ValueError('no valid trailing texture table')
    # Some suffixes also happen to have a matching count word. Preserve all
    # candidates in the inventory and cover the longest valid range.
    return candidates[0][0], candidates[0][1], [len(rows) for _, rows in candidates]


def world_record(row):
    page, clut = row[5], row[2]
    return (not (page & ~0x1ff) and 8 <= (page & 15) <= 14
            and (page >> 7) <= 1 and (clut & 63) >= 32 and (clut >> 6) < 512)


def box(uv):
    u, v = zip(*uv)
    return min(u), min(v), max(u) + 1, max(v) + 1


def connected(regions):
    clusters = []
    for bounds, owners in regions.items():
        while True:
            hit = next((i for i, (other, _) in enumerate(clusters) if overlaps(bounds, other)), None)
            if hit is None:
                break
            other, previous = clusters.pop(hit)
            bounds = (min(bounds[0], other[0]), min(bounds[1], other[1]),
                      max(bounds[2], other[2]), max(bounds[3], other[3]))
            owners = owners | previous
        clusters.append((bounds, owners))
    return clusters


def inventory_bank(bank, files, materials, existing, out):
    regions = defaultdict(lambda: defaultdict(set))
    stats = dict(bank=bank, worlds=[], models=0, model_errors=[], unresolved=[], references=0)
    if not {'A.RAW', 'B.RAW', 'MOD'} <= files.keys():
        stats['missing'] = sorted({'A.RAW', 'B.RAW', 'MOD'} - files.keys())
        return stats
    vram = vram_from_group(files)
    for name, data in files.items():
        if not re.fullmatch(r'LEVEL\d{2}', name):
            continue
        try:
            start, rows, candidates = world_table(data)
        except ValueError as error:
            stats['worlds'].append(dict(file=name, error=str(error)))
            continue
        stats['worlds'].append(dict(file=name, offset=start, count=len(rows), candidate_counts=candidates,
                                    sentinel_count=sum(not world_record(row) for row in rows)))
        for row in rows:
            if not world_record(row):
                continue
            a, b, clut, c, d, page, e, f, g, h = row
            regions[page & 0x19f, clut][box(((a,b),(c,d),(e,f),(g,h)))].add(name)
    mod = bytearray(files['MOD'])
    for model in range(2048):
        offset = struct.unpack_from('<i', mod, model * 4)[0]
        if offset == -1:
            continue
        try:
            if offset < 0:
                raise ValueError('negative model offset')
            mod[offset + 0x2007] = 0  # vertex count is u8, followed by flags
            parsed = parse_model(mod, model)
        except (ValueError, IndexError, KeyError, struct.error) as error:
            stats['model_errors'].append(dict(model=model, error=type(error).__name__))
            continue
        stats['models'] += 1
        for prim in parsed['prims']:
            if 'uv' in prim:
                regions[prim['tpage'] & 0x19f, prim['clut']][box(prim['uv'])].add(f'MOD:{model}')
    if files.get('HIE'):
        stats['hierarchies'] = {str(i): [j['model'] for j in h['joints']]
                                for i, h in parse_hierarchies(files['HIE']).items()}
    for (page, clut), boxes in regions.items():
        for bounds, owners in connected(boxes):
            u, v, right, bottom = bounds
            locator = dict(depth=(page >> 7) & 3, page_x=(page & 15)*64,
                           page_y=((page >> 4) & 1)*256, u=u, v=v, w=right-u, h=bottom-v,
                           cx=(clut & 63)*16, cy=clut >> 6, iw=right-u, ih=bottom-v)
            ref = dict(bank=bank, page=page, clut=clut, box=bounds, owners=sorted(owners))
            try:
                validate(locator, 2)
                image = Image.fromarray(texture_page(vram, page, clut)).crop(bounds)
            except (ValueError, IndexError) as error:
                stats['unresolved'].append(dict(**ref, reason=str(error)))
                continue
            # This bank dump does not contain the framebuffer or global font/HUD page.
            if locator['page_x'] < 512 or (locator['depth'] < 2 and locator['cx'] < 512):
                stats['unresolved'].append(dict(**ref, reason='source or palette outside bank upload'))
                continue
            if not image.getchannel('A').getbbox():
                stats['unresolved'].append(dict(**ref, reason='transparent in bank upload'))
                continue
            digest = hashlib.sha256(image.tobytes() + str(image.size).encode()).hexdigest()
            if digest not in materials:
                path = f'references/{digest}.png'
                image.save(out / path)
                materials[digest] = dict(sha256=digest, reference=path, size=image.size,
                                         existing_art=existing.get(digest), references=[])
            materials[digest]['references'].append(ref)
            stats['references'] += 1
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to((RECOMP/'analysis').resolve()):
        parser.error('output must be under recomp/analysis')
    (out/'references').mkdir(exist_ok=True, parents=True)
    coverage = json.loads((RECOMP/'analysis/level00-art-v2/coverage.json').read_text(encoding='utf-8'))
    existing = {r['sha256']: dict(id=m['id'], master=m['art_master'], cell=m['cell'])
                for m in coverage['materials'] for r in m['references'] if 'art_master' in m}
    disc = Disc(DISC_PATH)
    try:
        files = defaultdict(dict)
        common = []
        for entry in disc.files():
            match = GROUP.fullmatch(entry['path'])
            if match:
                bank, name = int(match[1]), match[2]
                short = name.removeprefix(f'DB{bank:02d}').removesuffix('.BIN')
                if short in ('A.RAW','B.RAW','MOD','HIE','TEXPOS.DAT') or re.fullmatch(r'LEVEL\d{2}', short):
                    files[bank][short] = disc.read(entry['lba'], entry['size'])
            elif entry['path'].startswith('/DATA/'):
                common.append(dict(path=entry['path'], size=entry['size']))
        for challenge, geometry in CHALLENGE_WORLDS.items():
            name = f'LEVEL{geometry:02d}'
            files[challenge][name] = files[geometry][name]
        materials = {}
        banks = [inventory_bank(bank, files[bank], materials, existing, out) for bank in sorted(files)]
    finally:
        disc.close()
    result = dict(banks=banks, common_files=common, materials=list(materials.values()))
    (out/'inventory.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(banks=len(banks), materials=len(materials),
                          reused=sum(bool(m['existing_art']) for m in materials.values()),
                          unresolved=sum(len(b['unresolved']) for b in banks),
                          model_errors=sum(len(b['model_errors']) for b in banks),
                          world_errors=[w for b in banks for w in b['worlds'] if 'error' in w])))


if __name__ == '__main__':
    main()
