"""Numerically check the real rasterizer against projective UV interpolation.

Only texture fetch/output are observed; interpolation and edge traversal come
from the production source. No disc, GPU context or player data is required.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'psxrecomp/runtime/src'

SHIM = r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "gpu_sw_edges.h"
typedef struct { int cx1,cy1,cx2,cy2; } RTarget;
static int g_texture_filter,g_mod_r,g_mod_g,g_mod_b,g_raw_texture;
static int max_i(int a,int b) {return a>b?a:b;}
static int min_i(int a,int b) {return a<b?a:b;}
static int observed_u[64][64],observed_v[64][64],seen[64][64];
static uint16_t texel_fetch(int u,int v,uint16_t page,uint16_t cx,uint16_t cy) {
    (void)page;(void)cx;(void)cy;return (uint16_t)((u&255)|((v&255)<<8));
}
static uint16_t texel_fetch_bilinear(float u,float v,uint16_t page,uint16_t cx,uint16_t cy) {
    return texel_fetch((int)u,(int)v,page,cx,cy);
}
static float bilinear_center_shift_for_target(const RTarget* t) {(void)t;return 0;}
static void put_textured(const RTarget* t,int x,int y,uint16_t texel,int r,int g,int b,int raw) {
    (void)t;(void)r;(void)g;(void)b;(void)raw;
    assert(x>=0 && x<64 && y>=0 && y<64);
    observed_u[y][x]=texel&255;observed_v[y][x]=texel>>8;seen[y][x]=1;
}
'''

MAIN = r'''
int main(void) {
    const int permutations[6][3]={{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
    const int xy[3][2]={{0,0},{64,0},{0,64}},uv[3][2]={{0,0},{128,0},{0,128}};
    const int samples[3][2]={{16,16},{8,24},{24,8}};
    const double weights[3][3]={{1,.25,.25},{1,.01,.001},{1,1,1}};
    int checks=0;
    for(int clipped=0;clipped<2;++clipped)for(int p=0;p<6;++p)
    for(int w=0;w<3;++w)for(int scaled=0;scaled<2;++scaled)for(int perspective=0;perspective<2;++perspective) {
        const int a=permutations[p][0],b=permutations[p][1],c=permutations[p][2];
        const double scale=scaled?0.0001:1;
        RTarget target={0,clipped?12:0,63,clipped?40:63};
        memset(seen,0,sizeof seen);
        raster_textured_triangle(&target,xy[a][0],xy[a][1],uv[a][0],uv[a][1],
            xy[b][0],xy[b][1],uv[b][0],uv[b][1],xy[c][0],xy[c][1],uv[c][0],uv[c][1],
            0,0,0,perspective,(float)(weights[w][a]*scale),(float)(weights[w][b]*scale),(float)(weights[w][c]*scale));
        for(int s=0;s<3;++s) {
            const int x=samples[s][0],y=samples[s][1];
            if(y<target.cy1 || y>target.cy2){assert(!seen[y][x]);continue;}
            assert(seen[y][x]);
            const double lambda[3]={1-(x+y)/64.0,x/64.0,y/64.0};
            double q=0,u=0,v=0;
            for(int i=0;i<3;++i) {
                const double weight=lambda[i]*(perspective?weights[w][i]:1);
                q+=weight;u+=weight*uv[i][0];v+=weight*uv[i][1];
            }
            const int eu=(int)floor(u/q+1e-6),ev=(int)floor(v/q+1e-6);
            // A floating-point value exactly at a texel boundary can truncate
            // one texel earlier; affine UVs at unequal depths differ far more.
            assert(abs(observed_u[y][x]-eu)<=1 && abs(observed_v[y][x]-ev)<=1);
            if(perspective && w==0 && s==0)assert(observed_u[y][x]==12 && observed_v[y][x]==12);
            if(!perspective && s==0)assert(observed_u[y][x]==32 && observed_v[y][x]==32);
            ++checks;
        }
        if(clipped)assert(!seen[8][8] && !seen[48][8]);
    }
    printf("Projective UVs: %d samples passed (depth ratios, ordering, clipping, affine fallback, normalized weights)\n",checks);
    return 0;
}
'''


class PerspectiveMappingTest(unittest.TestCase):
    def test_projective_uvs_match_independent_barycentric_reference(self):
        source = (RUNTIME / 'gpu_sw_renderer.c').read_text(encoding='utf-8')
        start = source.index('static void raster_textured_triangle(')
        end = source.index('\nvoid sw_draw_textured_triangle(', start)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            code = path / 'perspective.c'
            code.write_text(SHIM + source[start:end] + MAIN, encoding='utf-8')
            binary = path / ('perspective.exe' if os.name == 'nt' else 'perspective')
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2', '-I', str(RUNTIME),
                            str(code), '-lm', '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
