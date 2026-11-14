"""Run a bounded OpenGL graphics route with new private cards and settings.

Samples level entry views and a camera sweep; this does not certify complete
levels or campaign coverage. Never imports or writes the player's saves.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import shutil
import struct
import sys
import time

from capture_graphics_budget import find_near
from debug_client import request

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--settings-file', type=Path, default=ROOT / 'config/player-profiles.json')
    parser.add_argument('--port', type=int, default=9126)
    parser.add_argument('--levels', type=int, nargs='+', default=[0, 1, 6, 8, 9, 12, 21])
    parser.add_argument('--seconds', type=float, default=8)
    parser.add_argument('--warmup', type=float, default=1)
    parser.add_argument('--internal-scale', type=int, choices=(1, 2, 3, 4))
    parser.add_argument('--frame-rate', choices=('60','auto','120'))
    parser.add_argument('--view', choices=('first','third'))
    parser.add_argument('--fire', action='store_true', help='hold fire during the private camera sweep')
    parser.add_argument('--campaign-art-preview', action='store_true')
    parser.add_argument('--hud-hd', action='store_true')
    parser.add_argument('--1080p', dest='full_hd', action='store_true',
                        help='measure the actual borderless 1920x1080 drawable')
    parser.add_argument('--capture-hud-vram', action='store_true',
                        help='save and verify the first live HUD page for local texture authoring')
    parser.add_argument('--profile', action='store_true', help='record CPU phase and guest hot functions for each sample')
    parser.add_argument('--no-screenshots', action='store_true', help='measure cadence without synchronous framebuffer readback')
    parser.add_argument('--legacy-performance', action='store_true', help='private A/B: restore eager Windows polling, duplicated live water and old recovery')
    parser.add_argument('--run-stop', action='store_true', help='move forward during the first half, then stop while continuing to turn')
    parser.add_argument('--cease-fire', action='store_true', help='with --fire, stop firing halfway through the sweep')
    parser.add_argument('--test-checkpoint', type=Path, help='slot 00 checkpoint under analysis only; never player saves')
    args = parser.parse_args()
    if args.cease_fire and not args.fire:
        parser.error('--cease-fire requires --fire')
    if args.no_screenshots and args.capture_hud_vram:
        parser.error('--capture-hud-vram requires screenshots')
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to((ROOT / 'analysis').resolve()):
        parser.error('output must be a NEW directory under recomp/analysis')
    if not 1024 <= args.port <= 65535 or not 4 <= args.seconds <= 60 or not 0 <= args.warmup <= 60:
        parser.error('invalid port, sample duration (4..60 seconds) or warmup (0..60 seconds)')
    try:
        request({'cmd': 'frame'}, args.port)
    except OSError:
        pass
    else:
        parser.error('debug port already belongs to a running game')
    out.mkdir(parents=True)
    if args.test_checkpoint is not None:
        seed = args.test_checkpoint.resolve()
        if not seed.is_relative_to((ROOT / 'analysis').resolve()) or not seed.is_file() or not seed.name.endswith('_slot00.pst'):
            parser.error('checkpoint must be an existing private slot 00 under recomp/analysis')
        destination = out / 'cards' / seed.parent.name
        destination.mkdir(parents=True)
        shutil.copyfile(seed, destination / seed.name)
        sidecar = seed.with_suffix(seed.suffix + '.ttk')
        if sidecar.is_file():
            shutil.copyfile(sidecar, destination / sidecar.name)
    profile = json.loads(args.settings_file.read_text(encoding='utf-8'))
    profile['active'] = 'modernized'
    modern = profile['profiles']['modernized']
    if args.view is not None:
        modern['controls']['view'] = args.view
    modern['presentation'].update(renderer='opengl', display='windowed', window_width=960)
    if args.full_hd:
        modern['presentation'].update(display='borderless', window_width=1920)
        modern['controls'].update(widescreen='16:9', vsync='on')
    if args.internal_scale is not None:
        modern['presentation']['internal_scale'] = args.internal_scale
    # Keep accepted controls; run.py explicitly selects corrected graphics below.
    settings = out / 'profiles.json'
    settings.write_text(json.dumps(profile, indent=2), encoding='utf-8')
    steer = out / 'steer.input'
    steer.write_text('', encoding='ascii')
    env = dict(os.environ, SDL_AUDIODRIVER='dummy', DNTTK_TEST_INPUT=str(steer),
               DNTTK_TEST_UNCAPTURED='1', DNTTK_TEST_EDGES='1', DNTTK_TEST_ISOLATED='1')
    env.update(PSX_WIN_RENDER_EAGER_POLL='1' if args.legacy_performance else '0',
               DNTTK_WATER_REDRAW_ONLY='0' if args.legacy_performance else '1',
               DNTTK_REPLAY_RECOVERY_HEADROOM='0' if args.legacy_performance else '1')
    env.pop('DNTTK_DECAL_EXACT', None)
    env.pop('SDL_VIDEODRIVER', None)
    command = [sys.executable, str(ROOT / 'tools/local/run.py'), '--debug-port', str(args.port),
               '--settings-file', str(settings), '--memcard-dir', str(out / 'cards'),
               '--renderer', 'opengl', '--world-renderer', 'polymorph',
               '--geometry-precision', 'corrected', '--texture-precision', 'corrected']
    if args.frame_rate is not None:
        command += ['--frame-rate', args.frame_rate]
    if args.campaign_art_preview:
        command += ['--texture-set', 'realistic', '--antialias', 'smooth', '--campaign-art-preview', '--no-session-log']
    if args.hud_hd:
        command += ['--hud-hd']
    report = dict(passed=False, levels=[], limits='Entry views and short camera sweeps only; not full level coverage.')

    def call(cmd, **kw):
        result = request(dict(cmd=cmd, **kw), args.port)
        if not result.get('ok'):
            raise RuntimeError(result)
        return result

    def read(addr, length):
        return bytes.fromhex(call('read_ram', addr=hex(addr), len=length)['hex'])

    def state():
        half = lambda addr: int.from_bytes(read(addr, 2), 'little')
        return dict(mode=half(0x800bcbb0), phase=half(0x800ce1b0),
                    level=int.from_bytes(read(0x800be570, 4), 'little'),
                    end=read(0x800be55e, 1)[0], pause=half(0x800be568),
                    health=half(0x800d71ca))

    def live(s):
        return s['mode'] == 1 and s['phase'] == 2 and s['end'] == 1 and not s['pause']

    def snapshot():
        controls = call('ttk_input')['input']['controls']
        result = dict(time=time.monotonic(), field=call('frame')['frame'], cameras=controls['cameras'],
                    state=state(), near=find_near(controls),
                    geometry=call('geom_correction'), replay=call('render_replay'))
        result['first_person_requested'] = controls['fp']['requested']
        if args.view and live(result['state']) and result['first_person_requested'] != (args.view == 'first'):
            raise RuntimeError('Camera perspective changed during the private route; reject this measurement')
        if args.profile:
            result['cpu_phase'] = call('phase_profile', window=2)
            result['hot_static'] = call('phase_hot', set='static', top=64)
        return result

    def save(name, value):
        (out / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

    def capture(name):
        if args.no_screenshots:
            return
        if args.full_hd or args.frame_rate not in (None, '60'):
            # Replay restores live VRAM after presentation; the CPU/native VRAM
            # capture may legitimately be black when live drawing is suppressed.
            before = call('present_shot_seq')['seq']
            call('present_shot', path=(out / name).as_posix())
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                receipt = call('present_shot_seq')
                if receipt['seq'] > before:
                    if not receipt['wrote']:
                        raise RuntimeError('present surface capture failed')
                    if args.full_hd:
                        with (out / name).open('rb') as image:
                            header = image.read(24)
                        if struct.unpack('>II', header[16:24]) != (1920, 1080):
                            raise RuntimeError('test requires a 1920x1080 drawable')
                    return
                time.sleep(.05)
            raise TimeoutError('present surface capture')
        call('screenshot_file', path=str(out / name))

    process = None
    with (out / 'runtime.log').open('w', encoding='utf-8') as log:
        try:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log)
            deadline = time.monotonic() + 90
            while True:
                if process.poll() is not None:
                    raise RuntimeError('game exited during startup')
                try:
                    call('frame')
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError('debug server startup')
                    time.sleep(.25)
            # Synthetic input is confined to this new process, never the player's game.
            if args.test_checkpoint is not None:
                call('savestate', op='load', slot=0)
                time.sleep(1)
            while time.monotonic() < deadline:
                startup = state()
                if live(startup):
                    break
                if startup['mode'] not in (0, 1):
                    call('press', buttons=65527, frames=6) # skip startup movies
                steer.write_text('enter', encoding='ascii')
                time.sleep(.15)
                steer.write_text('', encoding='ascii')
                time.sleep(1)
            else:
                raise TimeoutError('new private game')
            steer.write_text('play', encoding='ascii')
            call('write_ram', addr='0x800c3cc6', val='1')
            call('write_ram', addr='0x800c3cc7', val='0')
            for level in args.levels:
                before_travel = snapshot()
                if state()['level'] != level:
                    reply = call('console', line=f'level {level}')
                    if 'Travelling to ' not in reply.get('reply', ''):
                        raise RuntimeError(reply)
                    deadline = time.monotonic() + 90
                    # Allow the queued engine restart to begin before checking completion.
                    time.sleep(1)
                    while time.monotonic() < deadline:
                        current = state()
                        if live(current) and current['level'] == level:
                            break
                        time.sleep(.25)
                    else:
                        raise TimeoutError(f'level {level}: {state()}')
                time.sleep(args.warmup)
                capture(f'level-{level}-entry.png')
                if args.capture_hud_vram and not report['levels']:
                    def hud_page():
                        words = []
                        for y in range(0, 256, 4):
                            packed = call('gl_fbo_peek', x=960, y=y, w=64, h=4)['hex']
                            words.extend(int(packed[i:i+4],16) for i in range(0,len(packed),4))
                        return struct.pack('<16384H', *words)
                    hud = hud_page()
                    if hud != hud_page():
                        raise RuntimeError('HUD page changed during capture')
                    (out/'hud-vram.raw').write_bytes(hud)
                # Readback and writing a Full HD PNG can block presentation.
                # Begin the measurement after the screenshot and its recovery.
                if not args.no_screenshots:
                    time.sleep(args.warmup)
                start = snapshot()
                deadline = time.monotonic() + args.seconds
                samples = []
                while time.monotonic() < deadline:
                    # Normal route rotates in place. The explicit run/stop case
                    # is confined to this private, invulnerable test process.
                    first_half = deadline-time.monotonic() > args.seconds/2
                    moving = args.run_stop and first_half
                    firing = args.fire and (first_half or not args.cease_fire)
                    steer.write_text('play dx=0.6' + (' w' if moving else '')
                                     + (' mouse1' if firing else ''), encoding='ascii')
                    time.sleep(1)
                    sample = snapshot()
                    sample['moving_requested'] = moving
                    sample['firing_requested'] = firing
                    samples.append(sample)
                steer.write_text('play', encoding='ascii')
                end = snapshot()
                capture(f'level-{level}-sweep.png')
                save(f'level-{level}.json', dict(before_travel=before_travel, start=start, end=end, samples=samples))
                near0, near1 = before_travel['near'], end['near']
                delta = {key: near1[key] - near0[key] for key in
                         ('budget_event_count', 'copy_overflows', 'packet_skips', 'mesh_fallbacks')}
                coverage = dict(
                    frames=end['near']['measure']['frames'] - start['near']['measure']['frames'],
                    depth_triangles=end['replay']['host_depth'][0] - start['replay']['host_depth'][0],
                    perspective_triangles=end['geometry']['perspective_triangles'] - start['geometry']['perspective_triangles'])
                corrected = end['geometry']['mesh']['geometry'] == 1 and end['geometry']['mesh']['textures'] == 1
                replay_ok = True
                if args.frame_rate not in (None, '60'):
                    replay_ok = (end['replay']['plugin']['interp']
                                 and end['replay']['plugin']['shown'] > start['replay']['plugin']['shown']
                                 and end['replay']['plugin']['rendered'] > start['replay']['plugin']['rendered']
                                 and end['replay']['workers'].get('draw_failed', 0) == 0)
                windows = [
                    (right['replay']['distinct'] - left['replay']['distinct'])
                    / (right['time'] - left['time'])
                    for left, right in zip([start, *samples], samples)
                ]
                divisors = [sample['replay']['plugin']['pace_div'] for sample in (start, *samples, end)]
                presentation_fps = (end['replay']['presents'] - start['replay']['presents']) / (end['time'] - start['time'])
                # Trace snapshots overlap, so count each presented camera sample once.
                camera_age = {}
                for sample in samples:
                    for entry in sample['replay']['plugin'].get('trace', '').split():
                        fields = entry.split('/')
                        if len(fields) == 11 and float(fields[-1]) >= 0:
                            camera_age[fields[8]] = float(fields[-1])
                ages = sorted(camera_age.values())
                row = dict(level=level, state=end['state'], changes=delta,
                           distinct_fps=round((end['replay']['distinct']-start['replay']['distinct'])
                                              / (end['time']-start['time']),2),
                           coverage=coverage, corrected=corrected,
                           presentation_fps=round(presentation_fps, 2),
                           min_sample_fps=round(min(windows), 2),
                           samples_below_50=sum(fps < 50 for fps in windows),
                           max_present_divisor=max(divisors),
                           camera_age_samples=len(ages),
                           camera_age_p95_ms=ages[math.ceil(len(ages)*.95)-1] if ages else None,
                           water_seen=end['near']['water']['seen'] - start['near']['water']['seen'],
                           replay_ok=replay_ok,
                           passed=live(end['state']) and end['state']['level'] == level
                           and corrected and replay_ok and all(v > 0 for v in coverage.values())
                           and all(v == 0 for v in delta.values()))
                report['levels'].append(row)
                save('results.json', report)
                print(json.dumps(row), flush=True)
            report['passed'] = all(row['passed'] for row in report['levels'])
        except Exception as error:
            report['error'] = str(error)
            print(f'ERROR: {error}', flush=True)
        finally:
            steer.write_text('', encoding='ascii')
            if process is not None and process.poll() is None:
                try:
                    request({'cmd': 'quit'}, args.port)
                    process.wait(timeout=15)
                except (OSError, subprocess.TimeoutExpired):
                    report['shutdown_incomplete'] = True
            report['exe_sha256'] = hashlib.sha256((ROOT / 'build-local/Duke_Nukem__Time_to_Kill_Recompiled.exe').read_bytes()).hexdigest()
            save('results.json', report)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
