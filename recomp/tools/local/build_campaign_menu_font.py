"""Compile both native menu sizes from the authored campaign glyph master."""
import argparse
import hashlib
import shutil
import struct
from pathlib import Path

import numpy as np
from PIL import Image

from build_campaign_glyphs import OUT, glyphs
from build_ttk_fonts import FONTS_PATH, FONTS_SHA256, Sheet
from disc_lab import Disc
from texture_sample import build
from ttk_anim import DISC_PATH, read_exe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-hud', action='store_true')
    parser.add_argument('--master', type=Path, default=OUT/'glyphs-master.png')
    args = parser.parse_args()
    disc = Disc(DISC_PATH)
    try:
        entry = next(e for e in disc.files() if e['path'] == FONTS_PATH)
        raw = disc.read(entry['lba'], entry['size'])
    finally:
        disc.close()
    if hashlib.sha256(raw).hexdigest() != FONTS_SHA256:
        raise ValueError('unexpected USA font texture')
    sheet = Sheet(raw)
    exe = read_exe()
    art = dict(glyphs(args.master))
    out = OUT/'menu-font'
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    # Keep the status bar as well when the two remastered UI packs are combined.
    if args.with_hud:
        hud = OUT/'hud'
        for name in (hud/'pack.ttkpack').read_text().splitlines()[1:]:
            shutil.copyfile(hud/name, out/name)
            files[name] = None
    base = 2048-0x80010000
    for font, height in ((0,11),(1,17)):
        for char in range(33,97):
            u,v,w,_ = struct.unpack_from('<4B',exe,base+0x800c3f30+256*font+4*char)
            band = range(72,107) if font==0 else range(0,72)
            if not w or v not in band or u+w>=256:
                continue
            words = [sheet.word(x,y) for y in range(v,v+height)
                     for x in range(960+u//4,960+(u+w+3)//4)]
            native = [sheet.texel(x,y) for y in range(v,v+height) for x in range(u,u+w)]
            for row in (225,226,227,239):
                palette = [sheet.word(1008+x,row) for x in range(16)]
                colors = sheet.palette(row)
                present = np.array([palette[x]!=0 for x in native]).reshape(height,w)
                if not present.any():
                    continue
                # Fit new ink to the existing glyph bearings. The native widths
                # still drive centering, hit targets and PT-BR accent placement.
                size = w*5,height*5
                if chr(char) in art:
                    ys,xs = np.nonzero(present)
                    bounds = (int(xs.min())*5,int(ys.min())*5,
                              int(xs.max()+1)*5,int(ys.max()+1)*5)
                    src = art[chr(char)].resize((bounds[2]-bounds[0],bounds[3]-bounds[1]),
                                                Image.Resampling.LANCZOS)
                    rgba = np.array(src)
                    if row!=225:
                        luma = np.asarray(src.convert('L'),dtype=np.float32)
                        ramp = np.asarray(colors[:15])
                        rgba[:,:,:3] = ramp[np.minimum(14,(luma/17.0).astype(int))]
                    tile = Image.new('RGBA',size)
                    tile.paste(Image.fromarray(rgba),bounds[:2])
                else:
                    tile = Image.new('RGBA',(w,height))
                    tile.putdata([(*colors[x],255 if palette[x] else 0) for x in native])
                    tile = tile.resize(size,Image.Resampling.LANCZOS)
                loc = dict(depth=0,page_x=960,page_y=0,u=u,v=v,w=w,h=height,
                           cx=1008,cy=row,iw=size[0],ih=size[1])
                payload = build(loc,words,palette,tile.tobytes(),3)
                name = 'glyph-'+hashlib.sha256(payload).hexdigest()[:20]+'.ttktx'
                (out/name).write_bytes(payload)
                files[name] = None
    manifest = out/('with-hud.ttkpack' if args.with_hud else 'menu.ttkpack')
    tmp = manifest.with_suffix('.tmp')
    tmp.write_bytes(('TTKPACK1\n'+'\n'.join(files)+'\n').encode('ascii'))
    tmp.replace(manifest)
    print(f'{len(files)} UI specimens in {manifest.name}')


if __name__ == '__main__':
    main()
