"""Compile exact PS1 HUD sprites with HD materials and native transparency."""
import argparse
import hashlib
from pathlib import Path
import struct

import numpy as np
from PIL import Image
from build_campaign_inventory_icons import OUT
from build_ttk_fonts import Sheet
from texture_sample import build, decode
from ttk_anim import read_exe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vram', type=Path, help='stable HUD page captured with check_graphics_route')
    sheet = Sheet(parser.parse_args().vram.read_bytes())
    if len(sheet.raw) != 64*256*2:
        raise ValueError('expected the 64-word HUD page at VRAM (960,0)')
    exe = read_exe()
    out = OUT/'hud'
    out.mkdir(exist_ok=True)
    with Image.open(OUT/'hud-materials.png') as master:
        w, h = master.size
        swatches = [master.crop((x*w//2, y*h//2, (x+1)*w//2, (y+1)*h//2)).convert('L')
                    for y in range(2) for x in range(2)]

    names = {}

    def add(name, u, v, w, h, clut, material, icon=None):
        cx, cy = (clut & 63)*16, clut >> 6
        loc = dict(depth=0,page_x=960,page_y=0,u=u,v=v,w=w,h=h,cx=cx,cy=cy,iw=w*6,ih=h*6)
        words = [sheet.word(x,y) for y in range(v,v+h) for x in range(960+u//4,960+(u+w+3)//4)]
        palette = [sheet.word(x,cy) for x in range(cx,cx+16)]
        rgb = decode(loc,words,palette,2)
        if not any(rgb):
            return
        size = loc['iw'],loc['ih']
        original = Image.frombytes('RGB',(w,h),rgb).resize(size,Image.Resampling.LANCZOS)
        if icon:
            # Keep the UV positions and make any unchanged native cutout edge
            # blend into the new icon instead of printing its transparent matte.
            with Image.open(OUT/icon) as artwork:
                artwork.thumbnail((size[0]*7//8,size[1]*7//8),Image.Resampling.LANCZOS)
                original.paste(artwork,((size[0]-artwork.width)//2,(size[1]-artwork.height)//2),artwork)
        grain = np.asarray(swatches[material].resize(size,Image.Resampling.LANCZOS),dtype=np.float32)
        gain = 1.06+(grain-grain.mean())/400
        pixels = np.clip(np.asarray(original)*gain[:,:,None],0,255).astype(np.uint8)
        payload = build(loc,words,palette,pixels.tobytes(),2)
        file = name+'-'+hashlib.sha256(payload).hexdigest()[:16]+'.ttktx'
        (out/file).write_bytes(payload)
        names[u,v,w,h,clut] = file

    # Status box, jetpack, mask, air, health, armour, goggles and ammo variants.
    for index in range(12):
        offset = 2048+0x800c44a4-0x80010000+index*16
        clut,w,h,x,y = struct.unpack_from('<HBBII',exe,offset)
        material = 1 if index == 4 else 2 if 7 <= index <= 10 else 3 if index in (3,5) else 0
        icon = {1:'inventory-1.png',2:'inventory-2.png',6:'inventory-3.png'}.get(index)
        add(f'box-{index}',(x-960)*4,y,w,h,clut,material,icon)

    # The stock seven-segment font is a lookup by ASCII in set 3. Keep the
    # warning/alternate palettes and their alpha rather than tinting at draw time.
    offset = 2048+0x800c4230-0x80010000
    for char in '0123456789%:-':
        u,v,w,_ = struct.unpack_from('<4B',exe,offset+ord(char)*4)
        if v != 109:
            raise ValueError('unexpected HUD glyph placement')
        for row in (227,228,229):
            add(f'counter-{ord(char)}-{row}',u,v,w,11,63+64*row,1)

    pending = out/'pack.tmp'
    pending.write_bytes(('TTKPACK1\n'+'\n'.join(names.values())+'\n').encode('ascii'))
    pending.replace(out/'pack.ttkpack')
    print(f'{len(names)} exact HUD texture regions')


if __name__ == '__main__':
    main()
