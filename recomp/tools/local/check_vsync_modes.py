"""Exercise VSync modes with private profiles/cards and driver readback logs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from debug_client import request

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    out=args.output.resolve()
    if out.exists() or not out.is_relative_to((ROOT/'analysis').resolve()):
        parser.error('output must be a new directory under analysis')
    out.mkdir(parents=True)
    checkpoint=ROOT/'analysis/remaster-pilot-original/cards/openbios/state_800AB6FC_slot00.pst'
    rows=[]
    for display,vsync,seconds in [('exclusive','off',5),('windowed','on',5),('borderless','on',5),('exclusive','on',60)]:
        name=f'{display}-{vsync}';folder=out/name
        command=[sys.executable,str(ROOT/'tools/local/texture_pilot.py'),'--output',str(folder),
                 '--texture-set','realistic','--antialias','smooth','--vsync',vsync,'--display',display,
                 '--checkpoint',str(checkpoint)]
        with (out/f'{name}-controller.log').open('w',encoding='utf-8') as log:
            process=subprocess.Popen(command,cwd=ROOT.parent,stdout=log,stderr=subprocess.STDOUT)
            try:
                deadline=time.monotonic()+100
                while time.monotonic()<deadline and not (folder/'ready.json').is_file():
                    if process.poll() is not None:raise RuntimeError(f'pilot failed: {name}')
                    time.sleep(.25)
                if not (folder/'ready.json').is_file():raise TimeoutError(name)
                text=(folder/'runtime.log').read_text(encoding='utf-8',errors='replace')
                value='1' if vsync=='on' else '0'
                assert f'ttk-display: vsync requested={value} applied={value}' in text,name
                if display=='exclusive':assert 'exclusive fullscreen mode' in text
                print(f'{name}: driver applied={value}',flush=True)
                subprocess.run([sys.executable,str(ROOT/'tools/local/measure_texture_pilot.py'),
                                '--output',str(folder/'measurement.json'),'--seconds',str(seconds),
                                '--warmup','20' if seconds==60 else '3'],cwd=ROOT.parent,check=True)
                summary=json.loads((folder/'measurement.json').read_text())['summary']
                assert summary['worker_failures']==0,name
                rows.append(dict(display=display,vsync=vsync,driver_interval=int(value),**summary))
            finally:
                if process.poll() is None:
                    try:request(dict(cmd='quit'),9131)
                    except (OSError,RuntimeError):pass
                process.wait(timeout=20)
        for path in [folder/'runtime.log',out/f'{name}-controller.log']:
            text=path.read_text(encoding='utf-8',errors='replace')
            for a,b in [(str(ROOT.parent),'.'),(ROOT.parent.as_posix(),'.'),(str(Path.home()),'~'),(Path.home().as_posix(),'~')]:text=text.replace(a,b)
            path.write_text(text,encoding='utf-8')
    report=dict(runs=rows,binary_sha256=hashlib.sha256((ROOT/'build-local/Duke_Nukem__Time_to_Kill_Recompiled.exe').read_bytes()).hexdigest(),
                limits=['Driver readback confirms swap interval; screenshots do not prove physical tear-free scanout',
                        'Short mode checks are smoke tests, not performance benchmarks',
                        'One-minute exclusive test follows warmup; no minimum FPS/campaign certification'])
    (out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('VSync mode checks complete',flush=True)


if __name__=='__main__':main()
