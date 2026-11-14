"""Exercise production GL depth state for water, decals and painter geometry.

Observes GL calls through a shim; framebuffer output needs in-game verification.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

SHIM = r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#define GL_TRUE 1
#define GL_FALSE 0
static int s_hz_valid, s_hz_clear_pending=1, clears, writes=1, colour=1;
static float s_hz[3];
static void hz_clear_area(void) { ++clears; s_hz_clear_pending=0; }
static void glDepthMask(int value) { writes=value; }
static void glColorMask(int r,int g,int b,int a) {
    assert(r==g && g==b && b==a); colour=r;
}
'''

MAIN = r'''
int main(void) {
    const float z[3]={8,32,4096};
    // Painter draws must not clear or write scene depth on admission.
    gl_set_host_depth(0,z); assert(!s_hz_valid && clears==0);
    // Corrected geometry uses monotonic reciprocal depth with a safe near clamp.
    gl_set_host_depth(1,z);
    assert(s_hz_valid==1 && clears==1 && s_hz[0]==0);
    assert(s_hz[1]==0.5f && s_hz[2]>s_hz[1] && s_hz[2]<1);
    // Arbitrary sequences must restore both masks after a run. In particular,
    // water tests without writing and decals write depth without drawing colour.
    for(int a=1;a<=3;++a) for(int b=1;b<=3;++b) {
        host_depth_run_state(a);
        assert(writes==(a!=2) && colour==(a!=3));
        host_depth_run_state(b);
        assert(writes==(b!=2) && colour==(b!=3));
        host_depth_run_end(); assert(writes && colour);
        gl_set_host_depth(b,z); assert(clears==1 && s_hz_valid==b);
    }
    // A new drawing area clears once on first depth geometry, including water.
    s_hz_clear_pending=1;
    gl_set_host_depth(0,z); assert(clears==1);
    gl_set_host_depth(2,z); assert(clears==2);
    gl_set_host_depth(3,z); assert(clears==2);
    for(int mode=-1;mode<=4;mode+=5) {
        gl_set_host_depth(mode,z);assert(!s_hz_valid);
    }
    return 0;
}
'''


class DepthModesTest(unittest.TestCase):
    def test_water_decal_masks_and_lazy_depth_clear(self):
        source = (ROOT / 'psxrecomp/runtime/src/gpu_gl_renderer.c').read_text(encoding='utf-8')
        start = source.index('void gl_set_host_depth(')
        end = source.index('\nuint64_t gl_host_depth_triangles', start)
        run = source.index('static int s_depth_only_run =')
        run_end = source.index('\nstatic void tex_batch_draw_passes', run)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            code = path / 'depth.c'
            code.write_text(SHIM + source[start:end] + source[run:run_end] + MAIN, encoding='utf-8')
            binary = path / ('depth.exe' if os.name == 'nt' else 'depth')
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2', str(code), '-lm', '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
