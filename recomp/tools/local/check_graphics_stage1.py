"""Check native clipping/decal contracts on the owned EXE, without running a game.

Build ttk-near-test first. Logs stay under analysis; no player saves are used.
These fixtures do not establish campaign-wide visual or performance correctness.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    binary = ROOT / 'build-local' / ('ttk-near-test.exe' if os.name == 'nt' else 'ttk-near-test')
    executable = ROOT / 'disc/SLUS_005.83'
    if not binary.is_file() or not executable.is_file():
        parser.error('build ttk-near-test and prepare your USA disc first')
    output = (args.output or ROOT / 'analysis' / ('graphics-stage1-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))).resolve()
    if not output.is_relative_to((ROOT / 'analysis').resolve()) or output.exists():
        parser.error('output must be a NEW directory under recomp/analysis')
    output.mkdir(parents=True)
    results = []
    cases = [(0, precision, '0', sky) for precision in ('original', 'corrected') for sky in ('0', '1')]
    cases += [(1, precision, exact, '1') for precision in ('original', 'corrected') for exact in ('auto', '0', '1')]
    for unified, precision, exact, sky in cases:
        env = dict(os.environ, DNTTK_UNIFIED_GEOMETRY=str(unified), DNTTK_GEOMETRY_PRECISION=precision,
                   DNTTK_TEXTURE_PRECISION=precision, DNTTK_SKY_PAINTER=sky)
        env.pop('DNTTK_DECAL_EXACT', None)
        if exact != 'auto':
            env['DNTTK_DECAL_EXACT'] = exact
        name = f'u{unified}-{precision}-exact{exact}-sky{sky}'
        run = subprocess.run([str(binary), str(executable)], env=env, capture_output=True, text=True, timeout=120)
        text = run.stdout + run.stderr
        (output / (name + '.log')).write_text(text, encoding='utf-8')
        def field(pattern):
            match = re.search(pattern, text)
            return match.group(1) if match else None
        result = dict(name=name, unified=unified, precision=precision, exact=exact, sky=sky,
                      returncode=run.returncode, passed=run.returncode == 0 and 'ttk-near-test PASS' in text,
                      packet_digest=field(r'packet_digest=(\w+)'), sky_digest=field(r'sky_projection_digest=(\w+)'),
                      projection_error=field(r'maximum_error=([0-9.]+)'))
        if unified:
            diagnostics = json.loads(field(r'budget_diagnostics=(.*)'))
            events = diagnostics['budget_events']
            result['budget_diagnostics_passed'] = (
                diagnostics['budget_event_count'] == 20 and len(events) == 16
                and all(e['reason'] == 'unified_downgrade' and e['required'] > e['available']
                        and e['mesh'] and e['caller'] and e['unified'] and not e['object'] for e in events))
            result['passed'] = result['passed'] and result['budget_diagnostics_passed']
        results.append(result)
        print(('PASS ' if result['passed'] else 'FAIL ') + name, flush=True)
    def case(unified, precision, exact, sky='1'):
        return next(r for r in results if (r['unified'], r['precision'], r['exact'], r['sky']) == (unified, precision, exact, sky))
    checks = []
    for precision in ('original', 'corrected'):
        a, b = case(0, precision, '0', '0'), case(0, precision, '0', '1')
        checks.append(bool(a['sky_digest']) and a['sky_digest'] == b['sky_digest'])
        reference = '0' if precision == 'original' else '1'
        a, b = case(1, precision, 'auto'), case(1, precision, reference)
        checks.append(bool(a['packet_digest']) and a['packet_digest'] == b['packet_digest'])
    corrected = case(1, 'corrected', 'auto')
    checks.append(corrected['projection_error'] is not None and float(corrected['projection_error']) <= 0.51 / 65536)
    passed = all(r['passed'] for r in results) and all(checks)
    (output / 'results.json').write_text(json.dumps(dict(passed=passed, cases=results, comparisons=checks,
        limits='Synthetic native fixtures; not a full-game visual or performance certification.'), indent=2) + '\n', encoding='utf-8')
    print(f'{len(results)} native cases; {sum(checks)}/{len(checks)} comparisons passed. Logs: {output}')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
