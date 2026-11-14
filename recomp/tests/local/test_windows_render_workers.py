"""Test the real Windows helper backend in separate processes, without a game."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SHIM = r'''
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <windows.h>
#include "cpu_state.h"
typedef int (*PSXModReplayDrawFn)(CPUState*,const void*,uint32_t);
typedef PSXModReplayDrawFn RenderWorkerDraw;
static RenderWorkerDraw s_boot_draw;
static void (*s_boot_prepare)(void);
static int s_visual_timing=1;
int g_render_replay_active,g_render_replay_record,psx_in_device_service;
int g_psx_render_untimed,g_psx_load_delay,g_psx_icache_active;
#define RW_MAX_WORKERS 2
#define RW_SLOTS 3
#define RW_JOBS 4
#define RW_PARAMS 64
#define RW_OUT_WORDS 64
#define RW_JOB_DEADLINE_MS 250
enum {RW_FREE,RW_QUEUED,RW_RUNNING,RW_DONE,RW_FAILED};
static uint32_t private_ram=17,*output;
static uint64_t SDL_GetPerformanceCounter(void){LARGE_INTEGER x;QueryPerformanceCounter(&x);return x.QuadPart;}
static uint64_t SDL_GetPerformanceFrequency(void){LARGE_INTEGER x;QueryPerformanceFrequency(&x);return x.QuadPart;}
static size_t render_replay_image_bytes(void){return sizeof private_ram;}
static void render_replay_image_save(uint8_t *p){memcpy(p,&private_ram,sizeof private_ram);}
static void render_replay_image_load(const uint8_t *p){memcpy(&private_ram,p,sizeof private_ram);}
static int psx_ws_x_margin(void){return 85;}
static void gpu_ws_set_margin_override(int margin){assert(margin==85);}
uint32_t psx_read_word(uint32_t address){return private_ram+address;}
uint16_t psx_read_half(uint32_t address){return (uint16_t)psx_read_word(address);}
uint8_t psx_read_byte(uint32_t address){return (uint8_t)psx_read_word(address);}
void psx_write_word(uint32_t a,uint32_t v){private_ram=v+a;}
void psx_write_half(uint32_t a,uint16_t v){psx_write_word(a,v);}
void psx_write_byte(uint32_t a,uint8_t v){psx_write_word(a,v);}
static void render_replay_reset_channel(void){}
void fntrace_enter_render_worker(void) {assert(g_render_replay_active && g_render_replay_record);}
static void render_replay_record_begin(uint32_t *p,uint32_t count){assert(count==64);output=p;}
static uint32_t render_replay_record_end(int *overflow){*overflow=0;return 1;}
static int render_replay_begin(void){return 1;}
static int render_replay_end(int ok){return ok;}
static int render_replay_feed(const uint32_t *p,uint32_t n){assert(n==1 && p[0]==123);return 1;}
static int gl_replay_set_capture_cache(int index){return index==1;}
static int gl_replay_cache_valid(int index){return index==1;}
static void gl_replay_reset_capture_cache(void){}
'''
MAIN = r'''
static int draw(CPUState *cpu,const void *params,uint32_t len){
    assert(g_render_replay_active && g_render_replay_record && psx_in_device_service);
    assert(len==sizeof(uint32_t));
    uint32_t value;memcpy(&value,params,len);
    if(value==999)Sleep(2600);
    assert(cpu->read_word(2)==19); // must point into this process despite ASLR
    cpu->write_word(0,99); // isolated child RAM, not the player's machine
    *output=cpu->gpr[4]+value;
    return 1;
}
int main(void){
    s_boot_draw=draw;
    if(render_worker_child_main())return 0;
    assert(psx_mod_replay_workers_start(2,draw)==2);
    ULONGLONG deadline=GetTickCount64()+10000;
    while((!w_load(&w_sh->ready[0]) || !w_load(&w_sh->ready[1])) && GetTickCount64()<deadline)Sleep(1);
    assert(w_load(&w_sh->ready[0]) && w_load(&w_sh->ready[1]));
    CPUState cpu={0};cpu.gpr[4]=100;
    cpu.read_word=(void*)1;cpu.write_word=(void*)1; // invalid in either process
    assert(!psx_mod_replay_publish(-1,&cpu));
    assert(psx_mod_replay_publish(0,&cpu));
    assert(w_sh->cpu[0].read_word==NULL && w_sh->cpu[0].write_word==NULL);
    // Status polling must not turn into a full process/job scan per query.
    // Subsequent timeout/restart checks below also exercise polling-only
    // watchdog progress, without any new submission to unstick a dead job.
    uint64_t checks_before=w_maintenance_calls;
    for(int i=0;i<100000;++i)assert(psx_mod_replay_job_state(0,NULL)==RW_FREE);
    assert(w_maintenance_calls-checks_before<10000);
    assert(w_state_queries>=100000);
    uint32_t param=23;
    assert(psx_mod_replay_submit(0,&param,RW_PARAMS+1,1)==-1);
    for(int iteration=0;iteration<20;++iteration){
        int job=psx_mod_replay_submit(0,&param,sizeof param,iteration+7);assert(job>=0);
        uint64_t tag=0;deadline=GetTickCount64()+5000;
        while(psx_mod_replay_job_state(job,&tag)<RW_DONE && GetTickCount64()<deadline)Sleep(1);
        assert(psx_mod_replay_job_state(job,&tag)==RW_DONE && tag==(uint64_t)iteration+7);
        assert(psx_mod_replay_render_job(job,1));
        assert(private_ram==17); // child writes never reach live memory
        psx_mod_replay_release(job);assert(psx_mod_replay_job_state(job,NULL)==RW_FREE);
    }
    // A stalled helper must fail within a bounded time and be terminated.
    param=999;int job=psx_mod_replay_submit(0,&param,sizeof param,99);assert(job>=0);
    deadline=GetTickCount64()+5000;
    while(psx_mod_replay_job_state(job,NULL)<RW_DONE && GetTickCount64()<deadline)Sleep(1);
    assert(psx_mod_replay_job_state(job,NULL)==RW_FAILED);
    int victim=w_sh->jobs[job].worker;
    assert(victim>=0 && w_restarts[victim]==1 && w_process[victim]);
    psx_mod_replay_release(job);
    param=23;job=psx_mod_replay_submit(0,&param,sizeof param,100);assert(job>=0);
    deadline=GetTickCount64()+5000;
    while(psx_mod_replay_job_state(job,NULL)<RW_DONE && GetTickCount64()<deadline)Sleep(1);
    assert(psx_mod_replay_job_state(job,NULL)==RW_DONE && psx_mod_replay_render_job(job,1));
    psx_mod_replay_release(job);
    HANDLE handles[2];
    for(int i=0;i<2;++i){handles[i]=NULL;if(w_process[i])assert(DuplicateHandle(GetCurrentProcess(),w_process[i],GetCurrentProcess(),&handles[i],SYNCHRONIZE,FALSE,0));}
    render_worker_shutdown();
    for(int i=0;i<2;++i)if(handles[i]){assert(WaitForSingleObject(handles[i],5000)==WAIT_OBJECT_0);CloseHandle(handles[i]);}
    puts("PASS: process isolation, ASLR callbacks, shared output, slot reuse, timeout, shutdown");
    return 0;
}
'''


@unittest.skipUnless(os.name == 'nt', 'Windows process backend')
class WindowsRenderWorkersTest(unittest.TestCase):
    def test_helpers_are_isolated_and_bounded(self):
        backend = (ROOT / 'psxrecomp/runtime/src/render_worker_win.h').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            code = path / 'workers.c'
            code.write_text(SHIM + backend + MAIN, encoding='utf-8')
            binary = path / 'workers.exe'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2', '-I', str(ROOT / 'psxrecomp/runtime/include'),
                            str(code), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=25)


if __name__ == '__main__':
    unittest.main()
