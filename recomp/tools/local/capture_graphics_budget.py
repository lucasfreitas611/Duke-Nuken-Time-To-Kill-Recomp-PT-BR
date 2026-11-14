"""Capture bounded graphics fallback diagnostics from a running local game."""
import argparse
import datetime
import json
from pathlib import Path

from debug_client import request


def find_near(value):
    if isinstance(value, dict):
        if 'budget_events' in value and 'scene_depth' in value:
            return value
        for child in value.values():
            result = find_near(child)
            if result is not None:
                return result
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=9123)
    args = parser.parse_args()
    response = request({'cmd': 'ttk_input'}, args.port)
    near = find_near(response)
    if not response.get('ok') or near is None:
        parser.error('game did not return graphics budget diagnostics')
    output = Path(__file__).resolve().parents[2] / 'analysis' / 'graphics-budget'
    output.mkdir(parents=True, exist_ok=True)
    path = output / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
    path.write_text(json.dumps(near, indent=2) + '\n', encoding='utf-8')
    print(f"Captured {len(near['budget_events'])} recent events; {near['budget_event_count']} total.")
    for event in near['budget_events']:
        print(f"{event['reason']}: mesh=0x{event['mesh']:08x}, caller=0x{event['caller']:08x}, "
              f"faces={event['faces']}, available={event['available']}, required={event['required']}")
    print(path.relative_to(Path(__file__).resolve().parents[2]))


if __name__ == '__main__':
    main()
