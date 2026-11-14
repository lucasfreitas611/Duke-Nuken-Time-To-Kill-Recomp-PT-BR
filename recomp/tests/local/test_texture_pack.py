"""Bounded multi-material registry, atomic failure and UV admission checks."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import test_texture_sample as fixture

sample,ROOT=fixture.sample,fixture.ROOT

CC=os.environ.get('CC','cc')


class TexturePackTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which(CC),'C compiler required')
    def test_registry_rejects_partial_traversal_and_overflow(self):
        code=r'''
#include "ttk_texture_pack.h"
#include <assert.h>
int main(int argc,char **argv) {
    TtkTextureSample s[TTK_TEXTURE_PACK_MAX]={0}; unsigned count=999;
    int expected=atoi(argv[2]);
    assert(ttk_texture_pack_load(argv[1],s,&count)==(expected>0));
    assert(count==(unsigned)expected);
    int valid[4]={1,0,1,1},before[4]={-1,1,0,-1};
    unsigned char touched[4]={0,1,1,1};
    ttk_texture_pack_replay_end(valid,before,touched,4);
    assert(valid[0]==1 && valid[1]==1 && valid[2]==0 && valid[3]==-1);
    if(!expected) for(unsigned i=0;i<TTK_TEXTURE_PACK_MAX;i++) assert(!s[i].source&&!s[i].palette&&!s[i].rgb);
    if(expected) {
        int u[3]={0,7,0},v[3]={16,16,23};
        assert(ttk_texture_pack_contains(&s[0],u,v,0));
        u[1]=8; assert(!ttk_texture_pack_contains(&s[0],u,v,0));
        assert(ttk_texture_pack_contains(&s[0],u,v,1));
        u[1]=9; assert(!ttk_texture_pack_contains(&s[0],u,v,1));
        u[1]=-1; assert(!ttk_texture_pack_contains(&s[0],u,v,0));
        for(unsigned i=0;i<count;i++) ttk_texture_sample_free(&s[i]);
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);src=p/'test.c';exe=p/('test.exe' if os.name=='nt' else 'test')
            src.write_text(code)
            subprocess.run([CC,'-std=c11','-I',str(ROOT/'psxrecomp/runtime/src'),str(src),'-o',str(exe)],check=True,capture_output=True)
            m,w,palette,rgb=fixture.TextureSampleTests().fixture()
            (p/'one.ttktx').write_bytes(sample.build(m,w,palette,rgb))
            cases=[('TTKPACK1\none.ttktx\none.ttktx\n',2),
                   ('TTKPACK1\none.ttktx\nmissing.ttktx\n',0),
                   ('TTKPACK1\n../one.ttktx\n',0),('TTKPACK1\n/one.ttktx\n',0),
                   ('TTKPACK1\none.ttktx',0),('TTKPACK1\n',0),
                   ('TTKPACK1\n'+'one.ttktx\n'*1024,1024),
                   ('TTKPACK1\n'+'one.ttktx\n'*1025,0),('WRONG\none.ttktx\n',0)]
            for text,expected in cases:
                with self.subTest(text=text[:50],expected=expected):
                    manifest=p/'pack.ttkpack';manifest.write_bytes(text.encode('ascii'))
                    subprocess.run([str(exe),str(manifest),str(expected)],check=True,capture_output=True)


if __name__=='__main__':
    unittest.main()
