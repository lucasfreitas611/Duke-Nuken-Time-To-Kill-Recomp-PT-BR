"""Rebuild the HD campaign banks against the locally verified USA disc."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from build_complete_texture_pack import dancer_tile
from disc_lab import Disc
from inventory_campaign_art import GROUP
from texture_sample import build, validate
from ttk_anim import DISC_PATH, vram_from_group

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'analysis/installed-art'
CAMPAIGN_UI = ('inventory-master.png', 'mission-cutout.png', 'hud-materials.png')


def prepare(archive_path, output):
    with ZipFile(archive_path) as archive, closing(Disc(DISC_PATH)) as disc:
        if all(f'ui/{name}' in archive.namelist() for name in CAMPAIGN_UI):
            ui = ROOT / 'analysis/campaign-art/ui'
            ui.mkdir(parents=True, exist_ok=True)
            for name in CAMPAIGN_UI:
                (ui / name).write_bytes(archive.read(f'ui/{name}'))
        banks = json.loads(archive.read('banks.json'))
        groups = {}
        for entry in disc.files():
            match = GROUP.fullmatch(entry['path'])
            if not match:
                continue
            name = match[2].removeprefix(f'DB{match[1]}')
            if name in ('A.RAW', 'B.RAW'):
                groups.setdefault(match[1], {})[name] = entry
        if set(banks) != {f'{i:02d}' for i in range(32)}:
            raise ValueError('Pacote de arte incompleto.')
        if 'fabric.png' in archive.namelist():
            with archive.open('fabric.png') as file, Image.open(file) as image:
                fabric = image.convert('L')
        else:
            fabric = None
        shared = output / 'specimens'
        shared.mkdir(parents=True, exist_ok=True)
        for bank, entries in banks.items():
            print(f'Preparando texturas HD do banco {bank} ({int(bank)+1}/32)', flush=True)
            vram = vram_from_group({
                name: disc.read(entry['lba'], entry['size'])
                for name, entry in groups[bank].items()
            })
            folder = output / bank
            folder.mkdir(exist_ok=True)
            names = []
            for locator, art in entries:
                texels_per_word, palette_size = validate(locator, 2)
                u, v, w, h = (locator[key] for key in ('u', 'v', 'w', 'h'))
                x = locator['page_x'] + u // texels_per_word
                y = locator['page_y'] + v
                width = (u % texels_per_word + w + texels_per_word - 1) // texels_per_word
                cx, cy = locator['cx'], locator['cy']
                words = vram[y:y+h, x:x+width].reshape(-1).tolist()
                palette = vram[cy, cx:cx+palette_size].tolist()
                if art is None:
                    if fabric is None:
                        raise ValueError('Acabamento de tecido ausente no pacote.')
                    page = locator['depth'] << 7 | locator['page_y'] // 256 << 4 | locator['page_x'] // 64
                    ref = dict(tpage=page, clut=cy << 6 | cx // 16, box=(u, v, u+w, v+h))
                    rgb = dancer_tile(vram, ref, fabric).tobytes()
                else:
                    rgb = archive.read(f'art/{art}.rgb')
                data = build(locator, words, palette, rgb, 2)
                name = hashlib.sha256(data).hexdigest() + '.ttktx'
                tile = shared / name
                if not tile.is_file():
                    tile.write_bytes(data)
                target = folder / name
                if not target.is_file():
                    try:
                        target.hardlink_to(tile)
                    except OSError:
                        target.write_bytes(data)
                names.append(name)
            manifest = folder / 'pack.ttkpack'
            temporary = manifest.with_suffix('.tmp')
            temporary.write_bytes(('TTKPACK1\n' + '\n'.join(names) + '\n').encode('ascii'))
            temporary.replace(manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    prepare(args.archive, OUTPUT)
