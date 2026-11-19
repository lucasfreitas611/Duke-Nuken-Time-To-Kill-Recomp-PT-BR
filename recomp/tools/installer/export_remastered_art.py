"""Export authored replacement pixels and bank coordinates from the local art review.

The Windows package contains no original VRAM words or palettes. The special
fabric treatment is rebuilt on the player's disc, using the authored fabric.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/local'))
from texture_sample import FIELDS, validate
from prepare_installed_art import CAMPAIGN_UI


def export(output):
    analysis = ROOT / 'analysis'
    maps = {}
    written = set()
    with ZipFile(output, 'x', ZIP_DEFLATED, compresslevel=3) as archive:
        for bank in range(32):
            folder = (analysis / 'campaign-art/packs' / f'{bank:02d}' if bank else
                      analysis / 'level00-realistic-complete')
            review = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
            files = (folder / 'pack.ttkpack').read_text().splitlines()[1:]
            by_name = {entry['file']: entry for entry in review['entries']}
            entries = []
            for name in files:
                review_entry = by_name[name]
                payload = (folder / name).read_bytes()
                if payload[:8] != b'TTKTX02\0':
                    raise ValueError(f'{name}: expected a reviewed RGB replacement')
                locator = dict(zip(FIELDS, struct.unpack_from('<11I', payload, 8)))
                ppw, pn = validate(locator, 2)
                stride = (locator['u'] % ppw + locator['w'] + ppw - 1) // ppw
                rgb = payload[52+2*(stride*locator['h']+pn):]
                if len(rgb) != locator['iw']*locator['ih']*3:
                    raise ValueError(f'{name}: invalid RGB payload')
                art = None
                if not review_entry.get('dancer_swimwear'):
                    art = hashlib.sha256(rgb).hexdigest()
                    if art not in written:
                        archive.writestr(f'art/{art}.rgb', rgb)
                        written.add(art)
                entries.append([locator, art])
            maps[f'{bank:02d}'] = entries
            print(f'{bank:02d}: {len(entries)} references, {len(written)} unique art tiles', flush=True)
        archive.write(analysis / 'level00-art-v2/dancer-swimwear-fabric.png', 'fabric.png')
        for name in CAMPAIGN_UI:
            archive.write(analysis / 'campaign-art/ui' / name, f'ui/{name}')
        archive.writestr('banks.json', json.dumps(maps, separators=(',', ':')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    export(args.output)
