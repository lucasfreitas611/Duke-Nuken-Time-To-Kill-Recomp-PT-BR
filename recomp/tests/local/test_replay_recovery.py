"""Exercise the production load controller with measured idle/feed budgets."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SHIM = r'''
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cassert>
static bool replay_on=true,interp_replay=true;
static bool late_camera(){return true;}
static bool continuous_timeline(){return true;}
static int pace_div=1,pace_clean=0,pace_backoff=1,target_hz=-2;
static uint64_t pace_presents=0,pace_bad=0,pace_changes=0,emu_sheds=0;
static int shed_steps=0,shed_backoff=1,shed_bad=0,shed_clean=0,shed_since_probe=1000,shed_full_clean=0;
static int shed_headroom_clean=0;
static double window_feed_sum=0,shed_feed_ms=0,seen_hz=30,feed_ms=2,response_slack=0;
static uint64_t window_feed_n=0,shed_failed_probes=0,shed_probes=0;
static int applied=1;
static void psx_mod_set_present_divisor(int d){applied=d;}
static void pace_log(const char*,double,int){}
'''
MAIN = r'''
static int window(int verdict){window_feed_sum=40;window_feed_n=20;return replay_load_window(verdict);}
static void overload(){assert(window(1)==0);assert(window(1)==1);assert(pace_div==2 && applied==2);}
int main(){
    overload();
    response_slack=4; // > twice the extra feed budget for 30 -> 60 plus margin
    window(0);assert(pace_div==2);
    response_slack=0.1;window(0);assert(pace_div==2);
    response_slack=4;window(0);assert(pace_div==2);
    window(0);assert(pace_div==1 && applied==1);
    assert(window(1)==1 && pace_div==2 && shed_backoff==2);
    for(int i=0;i<9;++i){window(0);assert(pace_div==2);}
    window(0);assert(pace_div==1);
    shed_backoff=1;
    shed_since_probe=1000;overload();
    response_slack=0.1;
    for(int i=0;i<29;++i){window(0);assert(pace_div==2);}
    window(0);assert(pace_div==1); // no headroom retains the conservative probe
    shed_since_probe=1000;overload();
    int age=shed_since_probe;
    for(int i=0;i<40;++i)window(2);
    assert(shed_since_probe==age && pace_div==2); // menus/loads aren't clean play
    seen_hz=60;response_slack=3;
    for(int i=0;i<5;++i){window(0);assert(pace_div==2);} // 60 -> 120 needs more CPU
    response_slack=8;
    for(int i=0;i<4;++i){window(0);assert(pace_div==2);}
    window(0);assert(pace_div==1);
    replay_on=false;int before=applied;
    assert(window(1)==-1 && applied==before); // original presentation unchanged
}
'''


class ReplayRecovery(unittest.TestCase):
    def test_real_controller_recovers_only_with_sustained_headroom(self):
        source = (ROOT / 'src/ttk/frame_replay.cpp').read_text(encoding='utf-8')
        begin = source.index('int replay_load_window(int window) {')
        end = source.index('\n// D17AR3: the live frame', begin)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            cpp = path / 'recovery.cpp'
            cpp.write_text(SHIM + source[begin:end] + MAIN, encoding='utf-8')
            binary = path / ('recovery.exe' if os.name == 'nt' else 'recovery')
            subprocess.run([os.environ.get('CXX', 'clang++'), '-std=c++17', str(cpp), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
