"""D16 specimen wire and exact-identity contract, without retail inputs or GL."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('texture_sample', ROOT/'tools/local/texture_sample.py')
sample = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sample)
COMPILER=os.environ.get('CC', 'cc')


class TextureSampleTests(unittest.TestCase):
    def fixture(self, depth=0):
        m=dict(depth=depth,page_x=640,page_y=0,u=0,v=16,w=8,h=8,cx=0,cy=300,iw=32,ih=32)
        ppw,pn=sample.validate(m)
        words=[0x1234]*(8//ppw*8)
        palette=list(range(pn))
        return m,words,palette,bytes([80,120,160])*32*32

    def test_region_validation_and_indexed_decode(self):
        m,w,p,rgb=self.fixture()
        self.assertEqual(sample.decode(m,w,p)[:6],bytes([32,0,0,24,0,0]))
        for change in ({'u':1},{'w':0},{'w':257},{'depth':3},{'cx':1020},{'page_x':1},
                       {'iw':2048},{'iw':31},{'ih':64},{'page_y':1},{'page_x':960,'depth':2,'w':128}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                sample.validate(dict(m,**change))

    def test_compile_master_to_bounded_runtime_scale_without_modifying_source(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            m,w,p,_=self.fixture()
            (root/'capture.json').write_text(json.dumps(dict(m,source_words=w,palette_words=p)))
            image=root/'master.png'
            Image.new('RGB',(97,97),(80,120,160)).save(image)
            before=image.read_bytes()
            output=root/'compiled.ttktx'
            command=[sys.executable,str(ROOT/'tools/local/texture_sample.py'),'compile',
                     str(root/'capture.json'),str(image),str(output),'--scale','2']
            subprocess.run(command,check=True,capture_output=True)
            payload=output.read_bytes()
            fields=struct.unpack_from('<11I',payload,8)
            self.assertEqual(fields[-2:],(16,16))
            native=struct.pack(f'<{len(w)+len(p)}H',*w,*p)
            self.assertEqual(payload[52:52+len(native)],native)
            self.assertEqual(len(payload),52+len(native)+16*16*3)
            self.assertEqual(image.read_bytes(),before)

    @unittest.skipUnless(shutil.which(COMPILER), 'C compiler required')
    def test_native_parser_identity_and_invalidation(self):
        code=r'''
#include "ttk_texture_sample.h"
#include <assert.h>
int main(int argc,char **argv) {
    TtkTextureSample s={0};
    int expected=atoi(argv[2]);
    assert(ttk_texture_sample_load(argv[1],&s)==expected);
    if(!expected) {assert(!s.source);return 0;}
    assert(s.iw==32&&s.ih==32);
    assert(ttk_texture_sample_equal(&s,s.source,s.palette));
    size_t n=s.words_w*s.h;
    uint16_t *changed=malloc(n*2);memcpy(changed,s.source,n*2);changed[n-1]^=1;
    assert(!ttk_texture_sample_equal(&s,changed,s.palette));free(changed);
    if(s.palette_n) {
        uint16_t p[256];memcpy(p,s.palette,s.palette_n*2);p[s.palette_n-1]^=0x8000;
        assert(!ttk_texture_sample_equal(&s,s.source,p));
        assert(ttk_texture_sample_intersects(&s,s.cx,s.cy,s.cx,s.cy));
    }
    assert(ttk_texture_sample_intersects(&s,s.x,s.y,s.x,s.y));
    assert(ttk_texture_sample_intersects(&s,s.x+s.words_w-1,s.y+s.h-1,s.x+s.words_w,s.y+s.h));
    assert(!ttk_texture_sample_intersects(&s,s.x+s.words_w,s.y,s.x+s.words_w,s.y));
    assert(!ttk_texture_sample_intersects(&s,0,0,10,10));
    ttk_texture_sample_free(&s);assert(!s.source&&!s.rgb);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'test.c').write_text(code)
            binary=d/('test.exe' if os.name=='nt' else 'test')
            subprocess.run([COMPILER,'-std=c11','-Wall','-Werror','-Wno-unused-parameter',
                            '-I',str(ROOT/'psxrecomp/runtime/src'),str(d/'test.c'),'-o',str(binary)],check=True)
            for depth in range(3):
                m,w,p,rgb=self.fixture(depth)
                data=sample.build(m,w,p,rgb)
                for name,payload,expected in [('valid',data,1),('short',data[:-1],0),('extra',data+b'x',0),
                                              ('magic',b'BADMAGIC'+data[8:],0),('huge',data[:44]+struct.pack('<I',0xffffffff)+data[48:],0)]:
                    with self.subTest(depth=depth,case=name):
                        (d/'sample').write_bytes(payload)
                        subprocess.run([str(binary),str(d/'sample'),str(expected)],check=True)


if __name__=='__main__':
    unittest.main()
