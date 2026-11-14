"""Measure a private texture pilot without enabling expensive forensic rings."""
import argparse
import json
from pathlib import Path
import time

from debug_client import request

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=9131)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--seconds', type=int, default=20)
    parser.add_argument('--warmup', type=int, default=10)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / 'analysis').resolve()) or output.exists():
        parser.error('output must be a new file under analysis')
    if not 5 <= args.seconds <= 120 or not 0 <= args.warmup <= 60:
        parser.error('invalid measurement duration')

    def call(cmd, **kw):
        value = request(dict(cmd=cmd, **kw), args.port)
        if not value.get('ok'):
            raise RuntimeError(value)
        return value

    def snap():
        replay = call('render_replay')
        return dict(time=time.monotonic(), field=call('frame')['frame'], replay=replay)

    time.sleep(args.warmup)
    start = snap()
    rows = []
    deadline = start['time'] + args.seconds
    while time.monotonic() < deadline:
        time.sleep(1)
        rows.append(snap())
    end = rows[-1]
    dt = end['time'] - start['time']
    summary = dict(seconds=round(dt, 3),
        fields_fps=round((end['field']-start['field'])/dt, 2),
        presents_fps=round((end['replay']['presents']-start['replay']['presents'])/dt, 2),
        distinct_fps=round((end['replay']['distinct']-start['replay']['distinct'])/dt, 2),
        worker_failures=end['replay']['workers'].get('draw_failed', 0),
        cadence=end['replay']['cadence'],
        ending_divisor=end['replay']['plugin']['pace_div'])
    output.write_text(json.dumps(dict(summary=summary, start=start, end=end, samples=rows), indent=2), encoding='utf-8')
    shot = output.with_suffix('.png')
    seq = call('present_shot_seq')['seq']
    call('present_shot', path=shot.as_posix())
    deadline = time.monotonic()+5
    while time.monotonic() < deadline:
        receipt = call('present_shot_seq')
        if receipt['seq'] > seq:
            if not receipt['wrote']:
                raise RuntimeError('present capture failed')
            break
        time.sleep(.1)
    else:
        raise TimeoutError('present capture')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
