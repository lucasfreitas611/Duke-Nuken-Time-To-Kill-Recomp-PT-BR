"""V2 partial VRAM words, arbitrary master dimensions and padded mip cells."""
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import test_texture_sample as fixture

CC=os.environ.get('CC','cc')


class CompleteTextureTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which(CC),'C compiler required')
    def test_v2_word_alignment_and_atlas_mip_isolation(self):
        code=r'''
#include "ttk_texture_atlas.h"
#include <assert.h>
int main(int argc,char **argv) {
    TtkTextureSample s={0}; int expected=atoi(argv[2]);
    assert(ttk_texture_sample_load(argv[1],&s)==expected);
    if(!expected){assert(!s.source&&!s.rgb);return 0;}
    assert(s.u==1&&s.w==7&&s.words_w==2&&s.x==640&&s.iw==313&&s.ih==314);
    assert(ttk_texture_sample_equal(&s,s.source,s.palette));
    assert(ttk_texture_sample_intersects(&s,641,20,641,20));
    assert(!ttk_texture_sample_intersects(&s,642,20,642,20));
    /* Solid colour survives padding and each level without adjacent-cell data. */
    unsigned char *p=ttk_texture_atlas_cell(&s,9,11,20,20,4); assert(p);
    unsigned w=20,h=20;
    for(unsigned level=0;level<3;level++) {
        for(unsigned i=0;i<w*h;i++) assert(p[i*3]==80&&p[i*3+1]==120&&p[i*3+2]==160);
        if(level<2){ttk_texture_atlas_reduce_channels(p,w,h,3);w/=2;h/=2;}
    }
    free(p);ttk_texture_sample_free(&s);
    /* Padding extrudes the nearest real edge, including corners. */
    unsigned char rgb[]={255,0,0,0,255,0,0,0,255,255,255,255};
    s.iw=s.ih=2;s.rgb=rgb;p=ttk_texture_atlas_cell(&s,2,2,12,12,4);assert(p);
    assert(p[0]==255&&p[1]==0&&p[2]==0);
    assert(p[(11*12+11)*3]==255&&p[(11*12+11)*3+1]==255);
    free(p);
    unsigned char rgba[]={255,0,0,0,255,0,0,255,255,0,0,0,255,0,0,255};
    s.rgba=1;s.rgb=rgba;p=ttk_texture_atlas_cell(&s,2,2,12,12,4);assert(p);
    assert(p[(4*12+4)*4+3]==0 && p[(4*12+5)*4+3]==255);
    ttk_texture_atlas_reduce_channels(p,12,12,4);
    assert(p[(2*6+2)*4+3]==128);
    free(p);
    TtkAtlasCell cells[]={{12,12,0,0,0},{16,24,0,0,1},{12,16,0,0,2}};
    assert(ttk_atlas_pack(cells,3,12)==0);
    assert(ttk_atlas_pack(cells,3,28)==36);
    assert(cells[0].index==1 && cells[0].x==0 && cells[0].y==0);
    assert(cells[1].index==2 && cells[1].x==16 && cells[1].y==0);
    assert(cells[2].index==0 && cells[2].x==0 && cells[2].y==24);
    return 0;
}
'''
        m=dict(depth=0,page_x=640,page_y=0,u=1,v=16,w=7,h=5,cx=0,cy=300,iw=313,ih=314)
        words=[0x1234]*10;palette=list(range(16));rgb=bytes([80,120,160])*313*314
        self.assertEqual(fixture.sample.decode(m,words,palette,2)[:3],bytes([24,0,0]))
        with self.assertRaises(ValueError):fixture.sample.validate(m)
        data=fixture.sample.build(m,words,palette,rgb,2)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);src=p/'test.c';exe=p/('test.exe' if os.name=='nt' else 'test')
            src.write_text(code)
            subprocess.run([CC,'-std=c11','-I',str(fixture.ROOT/'psxrecomp/runtime/src'),str(src),'-o',str(exe)],check=True,capture_output=True)
            for payload,expected in [(data,1),(data[:-1],0),(data+b'x',0),
                                     (b'TTKTX01\0'+data[8:],0),
                                     (data[:28]+struct.pack('<I',0)+data[32:],0)]:
                path=p/'v2.ttktx';path.write_bytes(payload)
                subprocess.run([str(exe),str(path),str(expected)],check=True,capture_output=True)


if __name__=='__main__':unittest.main()
