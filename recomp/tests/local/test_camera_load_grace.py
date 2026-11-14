"""Check the production rate governor using a controlled clock and guest state."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SHIM = r'''
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cassert>
#include <vector>
struct FakeClock {
    using time_point=std::chrono::steady_clock::time_point;
    static time_point value;
    static time_point now(){return value;}
};
FakeClock::time_point FakeClock::value;
static uint64_t fields=100;
static uint32_t level=0,loads=0;
static unsigned renewals=0;
static std::vector<int> verdicts;
static uint32_t psx_mod_read_word(uint32_t addr){assert(addr==0x800be570u);return level;}
static uint32_t psx_mod_savestate_loads(){return loads;}
static uint64_t input_host_frame(){return fields;}
static int replay_load_window(int verdict){verdicts.push_back(verdict);return 0;}
static void psx_overclock_renew(){++renewals;}
'''
MAIN = r'''
static void step(int ms,int delta){
    FakeClock::value+=std::chrono::milliseconds(ms);fields+=delta;overclock_lease();
}
int main(){
    step(100,0);
    step(1100,40);assert(verdicts.back()==2);
    step(1100,40);assert(verdicts.back()==2);
    step(1100,40);assert(verdicts.back()==1); // sustained deficit is judged
    ++level;step(500,0);
    step(1100,40);assert(verdicts.back()==2); // load stall cannot halve cadence
    step(1100,40);assert(verdicts.back()==2);
    step(1100,40);assert(verdicts.back()==1);
    step(1100,66);assert(verdicts.back()==0); // normal rate resumes judgement
    ++loads;step(1100,40);assert(verdicts.back()==2);
    step(1100,40);assert(verdicts.back()==2);
    step(1100,40);assert(verdicts.back()==2);
    step(1100,40);assert(verdicts.back()==1);
    step(4000,1);assert(verdicts.back()==2); // menu/long gap still excluded
    assert(renewals==14);
}
'''


class CameraLoadGraceTest(unittest.TestCase):
    def test_transition_grace_preserves_sustained_overload_detection(self):
        source = (ROOT / 'src/ttk/modern_controls.cpp').read_text(encoding='utf-8')
        begin = source.index('static void overclock_lease() {')
        end = source.index('\nstatic long frame_us;', begin)
        code = source[begin:end].replace('using clk=std::chrono::steady_clock;', 'using clk=FakeClock;')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            cpp = path / 'grace.cpp'
            cpp.write_text(SHIM + code + MAIN, encoding='utf-8')
            exe = path / ('grace.exe' if os.name == 'nt' else 'grace')
            subprocess.run([os.environ.get('CXX', 'clang++'), '-std=c++17', str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
