"""Exercise the actual renderer's tiled invalidation against exact intersections."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
CC=os.environ.get('CC','cc')


class TextureInvalidationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which(CC),'C compiler required')
    def test_tiled_candidates_never_miss_source_or_palette_writes(self):
        source=(ROOT/'psxrecomp/runtime/src/gpu_gl_renderer.c').read_text()
        functions=source[source.index('static void d16_index_rect('):source.index('static int d16_match(')]
        harness=r'''
#include "ttk_texture_pack.h"
#include <assert.h>
static TtkTextureSample s_d16[TTK_TEXTURE_PACK_MAX];
static unsigned s_d16_count=TTK_TEXTURE_PACK_MAX;
static uint64_t s_d16_tiles[256][TTK_TEXTURE_PACK_MAX/64];
static int s_d16_valid[TTK_TEXTURE_PACK_MAX],s_d16_in_replay=1;
static unsigned char s_d16_touched[TTK_TEXTURE_PACK_MAX];
'''+functions+r'''
int main(void) {
    uint16_t dummy=1;
    for(unsigned i=0;i<s_d16_count;i++) {
        TtkTextureSample *s=&s_d16[i];s->source=&dummy;
        s->x=(i*37)%1024;s->y=(i*11)%512;s->words_w=i%16+1;s->h=i%9+1;
        if(s->x+s->words_w>1024)s->words_w=1024-s->x;
        if(s->y+s->h>512)s->h=512-s->y;
        d16_index_rect(i,s->x,s->y,s->words_w,s->h);
        if(i%3) {s->palette_n=16;s->cx=(i*13)%1009;s->cy=(i*17)%512;
            d16_index_rect(i,s->cx,s->cy,16,1);}
    }
    for(int n=0;n<1024;n++) {
        int x0=(n*71)%1100-30,y0=(n*29)%550-20,x1=x0+n%81,y1=y0+n%47;
        if(n==0){x0=0;y0=0;x1=1023;y1=511;}
        if(n==1){x0=-300;y0=-200;x1=-1;y1=-1;}
        if(n==2){x0=100;y0=100;x1=99;y1=99;}
        for(unsigned i=0;i<s_d16_count;i++){s_d16_valid[i]=1;s_d16_touched[i]=0;}
        d16_invalidate(x0,y0,x1,y1);
        for(unsigned i=0;i<s_d16_count;i++) {
            int hit=ttk_texture_sample_intersects(&s_d16[i],x0,y0,x1,y1);
            assert(s_d16_valid[i]==(hit?-1:1));assert(s_d16_touched[i]==hit);
        }
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);src=p/'index.c';exe=p/('index.exe' if os.name=='nt' else 'index')
            src.write_text(harness)
            subprocess.run([CC,'-std=c11','-I',str(ROOT/'psxrecomp/runtime/src'),str(src),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,capture_output=True)


if __name__=='__main__':unittest.main()
