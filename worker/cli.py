"""python -m worker.cli 'your task' [--mock] [--run-dir DIR] [--approve writes|all] [--ui]"""
import argparse
import json
import sys

from . import config


def print_event(e):
    k = e.get('kind')
    if k == 'tool':
        res = e.get('result') or {}
        ok = 'ok ' if res.get('ok') else 'ERR'
        extra = '' if res.get('ok') else f" [{e.get('error_class')}]"
        retry = f" (attempt {e['attempt']})" if e.get('attempt', 1) > 1 else ''
        args = json.dumps(e.get('args'), default=str)
        print(f"  step {e['step']:>2} {ok} {e['tool']} {args[:110]}{extra}{retry}", flush=True)
    elif k == 'note':
        print(f"  step {e['step']:>2} ... {e['text'][:140]}", flush=True)
    elif k == 'verify':
        r = e['result']
        print(f"  verify: pass={r['pass']} live_checks={r['live_checks']} exact={r['exact_checks']} "
              f"failures={r['failures']}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description='AutoFlow_AI: autonomous AI task worker')
    ap.add_argument('goal')
    ap.add_argument('--run-dir')
    ap.add_argument('--max-steps', type=int, default=40)
    ap.add_argument('--max-cost', type=float, default=1.0, help='USD cap')
    ap.add_argument('--approve', choices=['auto', 'writes', 'all'], default='auto',
                    help='ask before commit-style actions (writes) or before every write (all)')
    ap.add_argument('--ui', action='store_true', help='ask via question.json/answer.json (Streamlit UI)')
    ap.add_argument('--mock', action='store_true',
                    help='offline plumbing demo: scripted policy instead of the model (no API key needed)')
    a = ap.parse_args(argv)

    from .agent import run
    from .asking import cli_ask, file_ask
    from pathlib import Path
    import time

    run_dir = Path(a.run_dir) if a.run_dir else config.ROOT / 'runs' / time.strftime('%Y%m%d-%H%M%S')
    run_dir.mkdir(parents=True, exist_ok=True)
    ask = file_ask(str(run_dir)) if a.ui else cli_ask

    llm = None
    if a.mock:
        from .llm import ScriptedLLM
        from .mock_policy import flagship_policy
        llm = ScriptedLLM(lambda: flagship_policy(a.goal))
    elif not config.GEMINI_API_KEY:
        sys.exit('GEMINI_API_KEY is not set. Put it in .env, or use --mock for the offline plumbing demo.')

    print(f'run dir: {run_dir}')
    rep = run(a.goal, llm=llm, ask=ask, run_dir=run_dir, max_steps=a.max_steps, max_cost=a.max_cost,
              approval_mode=a.approve, on_event=print_event)
    print('\n=== RESULT ===')
    print(f"status: {rep['status']}   verified: {rep['verification_passed']}   steps: {rep['steps']}   "
          f"retries: {rep['retries']}   cost: ${rep['cost_usd']}")
    print(rep['summary'])
    for v in rep['verified']:
        print(f"  [{'x' if v['match'] else ('?' if v['match'] is None else ' ')}] {v['criterion']}")
    print('evidence:', *rep['evidence'], sep='\n  ')
    return 0 if rep['status'] == 'done' else 1


if __name__ == '__main__':
    sys.exit(main())
