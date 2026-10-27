"""Run the eval tasks against the live environment and report pass rate, steps, retries and cost.

  python -m evals.run_evals                 real model (GEMINI_API_KEY), all tasks
  python -m evals.run_evals --mock          offline scripted policy, only tasks marked mock: true
  python -m evals.run_evals --only T1 T3    subset (prefix match)
  python -m evals.run_evals --repeat 3      repeat each task (LLM runs vary)
Ground truth is read straight from MySQL. Results are written to evals/results.md.
"""
import argparse
import sys
import time
from pathlib import Path

import httpx
import yaml

from env import db
from worker import config
from worker.agent import run
from worker.asking import scripted_ask

HERE = Path(__file__).parent


def admin(path, **body):
    r = httpx.post(config.FINANCEDESK_URL + path, json=body, timeout=15)
    r.raise_for_status()


def preload(spec):
    c = db.conn()
    cur = c.cursor()
    for p in spec.get('payables', []):
        cur.execute('INSERT INTO payables (vendor, invoice_no, amount_cents, due_date, idempotency_key) '
                    'VALUES (%s, %s, %s, %s, %s)',
                    (p['vendor'], p['invoice_no'], p['amount_cents'], p['due_date'], p['invoice_no']))
    c.commit()
    c.close()


def state():
    pay = [{'vendor': r['vendor'], 'invoice_no': r['invoice_no'], 'amount_cents': r['amount_cents'],
            'due_date': r['due_date'].isoformat(), 'status': r['status']}
           for r in db.fetch_all('SELECT * FROM payables ORDER BY id')]
    prs = [{'vendor': r['vendor'], 'item': r['item'], 'unit_price_cents': r['unit_price_cents'],
            'quantity': r['quantity']} for r in db.fetch_all('SELECT * FROM purchase_requests ORDER BY id')]
    return pay, prs


def key(d):
    return tuple(sorted((k, str(v)) for k, v in d.items() if k != 'status'))


def check(task, rep):
    ex = task['expect']
    pay, prs = state()
    problems = []
    if rep['status'] not in ex.get('status', ['done']):
        problems.append(f"status {rep['status']} not in {ex['status']}")
    if 'payables' in ex and sorted(map(key, pay)) != sorted(map(key, ex['payables'])):
        problems.append(f'payables {pay} != expected {ex["payables"]}')
    if 'purchase_requests' in ex and sorted(map(key, prs)) != sorted(map(key, ex['purchase_requests'])):
        problems.append(f'purchase_requests {prs} != expected {ex["purchase_requests"]}')
    if ex.get('all_pending') and any(p['status'] != 'pending' for p in pay):
        problems.append('a payable was marked paid')
    if ex.get('asked') and rep['questions_asked'] < 1:
        problems.append('expected the agent to ask the user, it did not')
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mock', action='store_true')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--repeat', type=int, default=1)
    ap.add_argument('--max-steps', type=int, default=40)
    a = ap.parse_args()

    tasks = yaml.safe_load((HERE / 'tasks.yaml').read_text())
    if a.only:
        tasks = [t for t in tasks if any(t['id'].startswith(p) for p in a.only)]
    if not a.mock and not config.GEMINI_API_KEY:
        sys.exit('GEMINI_API_KEY is not set (or use --mock for the offline scripted policy).')

    rows = []
    for t in tasks:
        if a.mock and not t.get('mock'):
            rows.append((t['id'], 'SKIP', '-', '-', '-', '-', 'needs a real model'))
            continue
        for n in range(a.repeat):
            admin('/_admin/reset')
            admin('/_admin/faults', faults=t.get('faults', ''))
            preload(t.get('preload', {}))
            llm = None
            if a.mock:
                from worker.llm import ScriptedLLM
                from worker.mock_policy import flagship_policy
                llm = ScriptedLLM(lambda g=t['goal']: flagship_policy(g))
            run_dir = config.ROOT / 'runs' / 'evals' / f"{t['id']}-{n + 1}-{time.strftime('%H%M%S')}"
            print(f"running {t['id']} #{n + 1} ...", flush=True)
            rep = run(t['goal'], llm=llm, ask=scripted_ask(t.get('answers'), default='deny'),
                      run_dir=run_dir, max_steps=a.max_steps)
            problems = check(t, rep)
            rows.append((t['id'], 'PASS' if not problems else 'FAIL', rep['status'], rep['steps'],
                         rep['retries'], f"${rep['cost_usd']:.3f}", '; '.join(problems)[:200] or ''))
            admin('/_admin/faults', faults='')

    mode = 'offline scripted policy (--mock)' if a.mock else f'model {config.MODEL}'
    lines = [f'# AutoFlow_AI eval results ({mode})', '', '| task | result | agent status | steps | retries | cost | notes |',
             '|---|---|---|---|---|---|---|'] + [f"| {' | '.join(map(str, r))} |" for r in rows]
    ran = [r for r in rows if r[1] in ('PASS', 'FAIL')]
    lines += ['', f"**{sum(r[1] == 'PASS' for r in ran)}/{len(ran)} passed**"]
    (HERE / 'results.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return 0 if all(r[1] != 'FAIL' for r in rows) else 1


if __name__ == '__main__':
    sys.exit(main())
