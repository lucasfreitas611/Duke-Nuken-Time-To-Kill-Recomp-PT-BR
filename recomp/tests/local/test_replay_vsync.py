"""VSync scheduling retains preparation time without accelerating ignored swaps."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
CC=os.environ.get('CC','cc')


class ReplayVSyncTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which(CC),'C compiler required')
    def test_blocking_swaps_and_refresh_cap(self):
        code=r'''
#include "replay_vsync.h"
#include <assert.h>
int main(void) {
    assert(replay_swap_target(120,60,1)==60);
    assert(replay_swap_target(120,60,0)==120);
    assert(replay_swap_target(30,60,1)==30);
    assert(replay_swap_target(240,0,1)==240);
    for(uint64_t period=4000;period<=34000;period+=1000) {
        for(uint64_t lag=0;lag<=period*4;lag+=137) {
            uint64_t at=100000,now=at+lag,old=at;
            do old+=period;while(old<=now);
            assert(replay_swap_deadline(at,now,now+period,period,1000000,0)==old);
            uint64_t done=now+period;
            uint64_t next=replay_swap_deadline(at,now,done,period,1000000,1);
            assert(next>=done+period*3/4); /* room for the next worker */
            assert(next>=at+period);       /* no faster if driver ignores sync */
        }
    }
    assert(replay_swap_deadline(100000,100000,100100,16667,1000000,1)==116667);
    assert(replay_swap_deadline(100000,100000,116667,16667,1000000,1)==131334);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);src=p/'test.c';exe=p/('test.exe' if os.name=='nt' else 'test')
            src.write_text(code)
            subprocess.run([CC,'-std=c11','-I',str(ROOT/'psxrecomp/runtime/src'),str(src),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,capture_output=True)


if __name__=='__main__':unittest.main()
