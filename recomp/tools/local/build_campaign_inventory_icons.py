"""Pack the five authored inventory icons into the existing TTKICO2 format."""
from pathlib import Path
import struct
import json
from PIL import Image
from build_ttk_mission_items import UI, entry, silhouette

RECOMP = Path(__file__).resolve().parents[2]
OUT = RECOMP/'analysis/campaign-art/ui'


def cells(master_path, columns, rows, count):
    with Image.open(master_path) as master:
        if master.mode != 'RGBA' or master.getchannel('A').getextrema()[0] != 0:
            raise ValueError(f'{master_path.name}: expected transparent RGBA')
        width, height = master.size
        for index in range(count):
            col, row = index%columns, index//columns
            icon = master.crop((round(col*width/columns), round(row*height/rows),
                                round((col+1)*width/columns), round((row+1)*height/rows)))
            bounds = icon.getchannel('A').getbbox()
            if not bounds:
                raise ValueError(f'empty icon {index+1}')
            yield icon.crop(bounds)


def main():
    original = (RECOMP/'build-local/ttk-inv-icons.pack').read_bytes()
    if original[:8] != b'TTKICO2\0':
        raise ValueError('invalid original icon pack')
    offset = 12
    entries = []
    icons = list(cells(OUT/'inventory-master.png', 3, 2, 5))
    for _ in range(struct.unpack_from('<I', original, 8)[0]):
        kind, item, tile, w, h = struct.unpack_from('<5H', original, offset)
        end = offset + 10 + 4*w*h
        if kind == 0 and 1 <= item <= 5:
            icon = icons[item-1]
            icon.thumbnail((36, 36), Image.Resampling.LANCZOS)
            icon.save(OUT/f'inventory-{item}.png')
            entries.append(struct.pack('<5H',kind,item,tile,*icon.size)+icon.tobytes())
        else:
            entries.append(original[offset:end])
        offset = end
    if offset != len(original):
        raise ValueError('unexpected icon pack trailer')
    (OUT/'ttk-inv-icons.pack').write_bytes(original[:12]+b''.join(entries))


def mission():
    names = ('subway-security-key', 'red-energy-crystal', 'blue-energy-crystal',
             'green-energy-crystal', 'skeleton-key', 'scrap-of-paper', 'old-note', 'family-jewel')
    icons = {}
    for name, icon in zip(names, cells(OUT/'mission-cutout.png', 4, 2, 8)):
        icon.thumbnail((32,32), Image.Resampling.LANCZOS)
        square = Image.new('RGBA', (32,32))
        square.paste(icon, ((32-icon.width)//2,(32-icon.height)//2))
        square.save(OUT/f'mission-{name}.png')
        icons[f'item-{name}.png'] = square.tobytes()
    items = json.loads((UI/'items/items.json').read_text(encoding='utf-8'))['items']
    entries = []
    for item in items:
        if item.get('hud') or item.get('gadget'):
            continue
        art = icons[item['file']]
        entries.extend((entry(0,item['name'],32,32,art),
                        entry(1,item['name'],32,32,silhouette(art))))
    old = (RECOMP/'build-local/ttk-mission-items.pack').read_bytes()
    if old[:8] != b'TTKMIS1\0':
        raise ValueError('invalid original mission icon pack')
    offset = 12
    for _ in range(struct.unpack_from('<I',old,8)[0]):
        kind, length = struct.unpack_from('<2H',old,offset)
        w,h = struct.unpack_from('<2H',old,offset+4+length)
        end = offset+8+length+w*h*4
        if kind >= 2:
            entries.append(old[offset:end])
        offset = end
    if offset != len(old):
        raise ValueError('unexpected mission icon pack trailer')
    (OUT/'ttk-mission-items.pack').write_bytes(old[:8]+struct.pack('<I',len(entries))+b''.join(entries))


if __name__ == '__main__':
    main()
    mission()
