"""Compile generated glyphs into the host font pack at its existing metrics."""
import struct
from pathlib import Path

import numpy as np
from PIL import Image
from build_campaign_inventory_icons import OUT, RECOMP, cells

# Measured row and column separators in the generated 1269x1239 atlas.
# The column boundaries are in deskewed coordinates so italic strokes fit.
ROWS = ((25,214), (243,435), (454,650), (665,849), (861,1042), (1053,1231))
COLUMNS = (
    (0,280,484,684,888,1087,1330),
    (0,259,489,651,865,1095,1330),
    (0,271,478,682,880,1097,1330),
    (0,254,457,657,856,1085,1330),
    (0,246,452,675,851,1073,1330),
    (0,250,449,657,858,1068,1330),
)
ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'


def glyphs(master_path=OUT/'glyphs-master.png'):
    with Image.open(master_path) as master:
        if master.mode != 'RGBA' or master.size != (1269,1239):
            raise ValueError('unexpected glyph master layout')
        x, y = np.meshgrid(np.arange(master.width), np.arange(200))
        deskewed = x + y*.28
        for row, (top, bottom) in enumerate(ROWS):
            pixels = np.array(master.crop((0,top,master.width,bottom)))
            u = deskewed[:bottom-top]
            for col, (left, right) in enumerate(zip(COLUMNS[row], COLUMNS[row][1:])):
                tile = pixels.copy()
                tile[(u < left) | (u >= right), 3] = 0
                image = Image.fromarray(tile)
                bounds = image.getchannel('A').getbbox()
                if not bounds:
                    raise ValueError('empty glyph cell')
                yield ALPHABET[row*6+col], image.crop(bounds)


def pack():
    art = dict(glyphs())
    original = (RECOMP/'build-local/ttk-fonts.pack').read_bytes()
    if original[:8] != b'TTKFONT2':
        raise ValueError('invalid base font pack')
    source = original[16:]
    count, = struct.unpack_from('<I',source)
    stride = 8 + 95*8
    metadata = bytearray(source[:4+count*stride])
    pixels = bytearray()
    for font in range(count):
        for index in range(95):
            record = 4 + font*stride + 8 + index*8
            w,h,_,_,old = struct.unpack_from('<4BI',source,record)
            color = source[old:old+w*h*4]
            char = chr(index+32).upper()
            if font < 7 and char in art:
                glyph = art[char].resize((w,h), Image.Resampling.LANCZOS)
                rgba = np.array(glyph)
                if font in (0,2):
                    # Match the existing steel font sets in the console/messages.
                    brightness = np.array(glyph.convert('L'), dtype=np.float32)/255
                    rgba[:,:,:3] = brightness[:,:,None]*np.array([175,200,246], dtype=np.float32)
                color = rgba[:,:,[2,1,0,3]].tobytes()
            struct.pack_into('<I',metadata,record+4,len(metadata)+len(pixels))
            pixels.extend(color)
    payload = metadata + pixels
    checksum = 2166136261
    for byte in payload:
        checksum = ((checksum ^ byte)*16777619)&0xffffffff
    (OUT/'ttk-fonts.pack').write_bytes(b'TTKFONT2'+struct.pack('<II',len(payload),checksum)+payload)


def weapon_icons():
    names = ('boot','knife','axe','desert-eagle','shotgun','gatling','rpg','pipe-bomb',
             'dynamite','holy-grenade','energy','flamethrower','buffalo','crossbow','freezer')
    for name, sprite in zip(names,cells(OUT/'weapons-master.png',4,4,len(names))):
        sprite.thumbnail((64,64),Image.Resampling.LANCZOS)
        sprite.save(OUT/f'weapon-{name}.png')


if __name__ == '__main__':
    pack()
    weapon_icons()
