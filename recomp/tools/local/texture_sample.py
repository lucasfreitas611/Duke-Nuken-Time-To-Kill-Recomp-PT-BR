#!/usr/bin/env python3
"""D16 local specimen: inspect/export a VRAM region, then compile edited RGB art.

Retail-derived captures and specimens belong in ignored analysis/, never Git.
This is a developer input, not a mod pack format. Renderer contract: one region,
exact source and CLUT identity, nearest RGB replacement, native cutout/STP.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

FIELDS = ('depth', 'page_x', 'page_y', 'u', 'v', 'w', 'h', 'cx', 'cy', 'iw', 'ih')


def validate(m, version=1):
    for key in FIELDS:
        if type(m.get(key)) is not int or m[key] < 0:
            raise ValueError(f'{key}: nonnegative integer required')
    d, px, py, u, v, w, h, cx, cy, iw, ih = (m[k] for k in FIELDS)
    if d > 2 or px > 960 or px % 64 or py not in (0, 256):
        raise ValueError('invalid texture page/depth')
    if not (0 <= u < 256 and 0 <= v < 256 and 1 <= w <= 256-u and 1 <= h <= 256-v):
        raise ValueError('region must fit one non-wrapping texture page')
    ppw = 4 >> d
    pn = (16, 256, 0)[d]
    if (version == 1 and (u % ppw or w % ppw)) or px + (u+w+ppw-1)//ppw > 1024 or py+v+h > 512:
        raise ValueError('region must be word-aligned and fit VRAM')
    if cx > 1023 or cy > 511 or cx+pn > 1024:
        raise ValueError('CLUT must fit one VRAM row')
    if not (1 <= iw <= 1024 and 1 <= ih <= 1024) or (version == 1 and (iw % w or ih % h or iw//w != ih//h)):
        raise ValueError('replacement needs uniform integer scale, at most 1024x1024')
    return ppw, pn


def decode(m, words, palette, version=1):
    ppw, pn = validate(m,version)
    stride=(m['u']%ppw+m['w']+ppw-1)//ppw
    if len(words) != stride*m['h'] or len(palette) != pn:
        raise ValueError('source/CLUT word count mismatch')
    rgb = bytearray()
    for y in range(m['h']):
        for x in range(m['w']):
            xx=x+m['u']%ppw
            word = words[y*stride+xx//ppw]
            raw = palette[(word >> ((xx % ppw)*(16//ppw))) & ((1 << (16//ppw))-1)] if pn else word
            rgb.extend(((raw >> shift) & 31)*255//31 for shift in (0, 5, 10))
    return bytes(rgb)


def build(m, words, palette, pixels, version=1):
    if version not in (1,2,3): raise ValueError('unsupported specimen version')
    ppw, pn = validate(m,version)
    stride = (m['u']%ppw+m['w']+ppw-1)//ppw
    if len(words) != stride*m['h'] or len(palette) != pn:
        raise ValueError('source/CLUT word count mismatch')
    if len(pixels) != m['iw']*m['ih']*(4 if version==3 else 3):
        raise ValueError('replacement pixel size mismatch')
    return f'TTKTX{version:02}\0'.encode('ascii') + struct.pack('<11I', *(m[k] for k in FIELDS)) + struct.pack(f'<{len(words)+len(palette)}H', *words, *palette) + pixels


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    cap = sub.add_parser('capture')
    cap.add_argument('--port', type=int, required=True)
    cap.add_argument('--region', type=int, nargs=9, required=True,
                     metavar=('DEPTH','PAGE_X','PAGE_Y','U','V','W','H','CLUT_X','CLUT_Y'))
    cap.add_argument('--output', type=Path, required=True)
    compile_p = sub.add_parser('compile')
    compile_p.add_argument('capture', type=Path)
    compile_p.add_argument('image', type=Path)
    compile_p.add_argument('output', type=Path)
    compile_p.add_argument('--scale', type=int, choices=range(1, 33),
                           help='compile the authored master at this integer native scale; source PNG is unchanged')
    a = p.parse_args()
    from PIL import Image
    if a.command == 'capture':
        from debug_client import request
        m = dict(zip(FIELDS[:9], a.region))
        m.update(iw=m['w'], ih=m['h'])
        ppw, pn = validate(m)
        def read(x,y,w,h):
            result = []
            for yy in range(y,y+h):
                for xx in range(x,x+w,128):
                    r=request(dict(cmd='gl_fbo_peek',x=xx,y=yy,w=min(128,x+w-xx),h=1), a.port)
                    if not r.get('ok'): raise RuntimeError(r)
                    result.extend(int(r['hex'][i:i+4],16) for i in range(0,len(r['hex']),4))
            return result
        words=read(m['page_x']+m['u']//ppw,m['page_y']+m['v'],m['w']//ppw,m['h'])
        palette=read(m['cx'],m['cy'],pn,1) if pn else []
        if words != read(m['page_x']+m['u']//ppw,m['page_y']+m['v'],m['w']//ppw,m['h']) or (pn and palette != read(m['cx'],m['cy'],pn,1)):
            raise ValueError('texture changed during capture; choose a stable state and retry')
        pixels=decode(m,words,palette)
        a.output.mkdir(parents=True,exist_ok=True)
        Image.frombytes('RGB',(m['w'],m['h']),pixels).save(a.output/'original.png')
        m.update(source_words=words,palette_words=palette,
                 source_sha256=hashlib.sha256(struct.pack(f'<{len(words)+len(palette)}H',*words,*palette)).hexdigest())
        (a.output/'capture.json').write_text(json.dumps(m,indent=2)+'\n')
        print(a.output/'capture.json')
    else:
        m=json.loads(a.capture.read_text())
        with Image.open(a.image) as image:
            if 'A' in image.getbands() and image.getchannel('A').getextrema() != (255,255):
                raise ValueError('RGB-only foundation: original game controls transparency; export opaque RGB art')
            # Authoring masters need not have runtime dimensions. Normalize
            # only the compiled RGB payload to a bounded, explicit texel budget.
            if a.scale:
                from PIL import Image
                target = (m['w']*a.scale, m['h']*a.scale)
                if max(target) > 1024:
                    raise ValueError('compiled texture exceeds 1024x1024 budget')
                image = image.resize(target, Image.Resampling.LANCZOS)
            m.update(iw=image.width,ih=image.height)
            validate(m)
            data=build(m,m['source_words'],m['palette_words'],image.convert('RGB').tobytes())
        a.output.write_bytes(data)
        print(f'{a.output}: {len(data)} bytes; {m["w"]}x{m["h"]} -> {m["iw"]}x{m["ih"]}')


if __name__ == '__main__':
    main()
