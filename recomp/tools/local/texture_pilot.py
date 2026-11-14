"""Open a reproducible texture pilot with new private cards and a checkpoint.

Retail-derived art, snapshots and profiles remain under ignored analysis/.
The existing debug API can inspect/capture/measure this process and quit it.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

from debug_client import request

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--port', type=int, default=9131)
    parser.add_argument('--sample', type=Path)
    parser.add_argument('--texture-set', choices=('original','realistic'), default='original')
    parser.add_argument('--vsync', choices=('on','off'), default='on')
    parser.add_argument('--campaign-art-preview', action='store_true')
    parser.add_argument('--display', choices=('windowed','borderless','exclusive'), default='windowed')
    parser.add_argument('--antialias', choices=('off','smooth'), default='off')
    parser.add_argument('--checkpoint', type=Path)
    parser.add_argument('--inspect-stream', action='store_true', help='expensive GP0 diagnostics, never for performance measurement')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to((ROOT / 'analysis').resolve()):
        parser.error('output must be a NEW directory under recomp/analysis')
    if not 1024 <= args.port <= 65535:
        parser.error('invalid debug port')
    try:
        connection = socket.create_connection(('127.0.0.1', args.port), timeout=3)
    except ConnectionRefusedError:
        pass
    except OSError as error:
        parser.error('cannot establish debug port availability: ' + str(error))
    else:
        connection.close()
        parser.error('debug port already in use')
    output.mkdir(parents=True)
    settings = json.loads((ROOT / 'config/mouse-smooth.json').read_text(encoding='utf-8'))
    settings['active'] = 'modernized'
    profile = settings['profiles']['modernized']
    profile['presentation'].update(renderer='opengl', internal_scale=2, display=args.display, window_width=1280)
    profile['controls'].update(frame_rate='auto', view='first', geometry_precision='corrected', texture_precision='corrected', texture_set=args.texture_set, antialias=args.antialias, vsync=args.vsync)
    config = output / 'profiles.json'
    config.write_text(json.dumps(settings, indent=2), encoding='utf-8')
    steer = output / 'steer.input'
    steer.write_text('', encoding='ascii')
    if args.checkpoint:
        checkpoint = args.checkpoint.resolve()
        if not checkpoint.is_relative_to((ROOT / 'analysis').resolve()) or not checkpoint.name.endswith('_slot00.pst') or not checkpoint.is_file():
            parser.error('checkpoint must be a private slot00 under analysis')
        destination = output / 'cards' / checkpoint.parent.name
        destination.mkdir(parents=True)
        shutil.copyfile(checkpoint, destination / checkpoint.name)
        extra = checkpoint.with_suffix(checkpoint.suffix + '.ttk')
        if extra.is_file():
            shutil.copyfile(extra, destination / extra.name)
    env = dict(os.environ, SDL_AUDIODRIVER='dummy', DNTTK_TEST_INPUT=str(steer),
               DNTTK_TEST_UNCAPTURED='1', DNTTK_TEST_EDGES='1', DNTTK_TEST_ISOLATED='1',
               PSX_FORENSICS='1' if args.inspect_stream else '0')
    for key in ('DNTTK_TEXTURE_SAMPLE', 'DNTTK_TEXTURE_PACK', 'SDL_VIDEODRIVER', 'DNTTK_LATE_TEST_YAW_FILE'):
        env.pop(key, None)
    if args.sample:
        sample = args.sample.resolve()
        if not sample.is_file() or not sample.is_relative_to((ROOT / 'analysis').resolve()):
            parser.error('pilot sample must be under analysis')
        env['DNTTK_TEXTURE_SAMPLE'] = str(sample)
    command = [sys.executable, str(ROOT / 'tools/local/run.py'), '--settings-file', str(config),
               '--memcard-dir', str(output / 'cards'), '--debug-port', str(args.port), '--no-session-log']
    if args.campaign_art_preview:
        command.append('--campaign-art-preview')

    def call(cmd, **kw):
        result = request(dict(cmd=cmd, **kw), args.port)
        if not result.get('ok'):
            raise RuntimeError(result)
        return result

    def half(address):
        return int.from_bytes(bytes.fromhex(call('read_ram', addr=hex(address), len=2)['hex']), 'little')

    def live():
        return half(0x800bcbb0) == 1 and half(0x800ce1b0) == 2 and half(0x800be55e) & 255 == 1 and half(0x800be568) == 0

    process = None
    with (output / 'runtime.log').open('w', encoding='utf-8') as log:
        try:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log)
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('pilot exited during startup')
                try:
                    call('frame')
                    break
                except OSError:
                    time.sleep(.25)
            else:
                raise TimeoutError('debug server startup')
            if args.checkpoint:
                call('savestate', op='load', slot=0)
            while time.monotonic() < deadline and not live():
                if half(0x800bcbb0) not in (0, 1):
                    call('press', buttons=65527, frames=6)
                steer.write_text('enter', encoding='ascii')
                time.sleep(.15)
                steer.write_text('', encoding='ascii')
                time.sleep(.7)
            if not live():
                raise TimeoutError('private new game')
            steer.write_text('play', encoding='ascii')
            call('write_ram', addr='0x800c3cc6', val='1')
            call('write_ram', addr='0x800c3cc7', val='0')
            time.sleep(4)
            if not args.checkpoint:
                call('savestate', op='save', slot=0)
            ready = dict(port=args.port, sample=bool(args.sample), first_person=call('ttk_input')['input']['controls']['fp']['requested'])
            (output / 'ready.json').write_text(json.dumps(ready, indent=2), encoding='utf-8')
            print(json.dumps(ready), flush=True)
            process.wait()
            return process.returncode
        finally:
            steer.write_text('', encoding='ascii')
            if process and process.poll() is None:
                try:
                    call('quit')
                except (OSError, RuntimeError):
                    pass
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
