"""The agent loop: Plan -> Act -> Observe -> Reflect -> Verify.

Nothing in this file knows about invoices. Task knowledge lives in the goal text, the system prompt's
description of available systems, and the tools.
"""
import collections
import json
import time
from pathlib import Path

from . import config
from .asking import cli_ask
from .context import CTX
from .errors import HINTS, RETRYABLE, classify
from .gate import check_gate
from .memory import Memory
from .prompts import system_prompt
from .tools import REGISTRY, specs
from .trace import Trace
from .verifier import verify

RETRY_BASE = 0.5   # seconds; tests set this to 0


def execute(call, mem, trace, ask, approval_mode='auto'):
    """Run one tool call: gate, run, classify errors, auto-retry idempotent/retryable failures."""
    t = REGISTRY.get(call.name)
    if t is None:
        return {'ok': False, 'error_class': 'bad_input', 'error': f'unknown tool {call.name}',
                'hint': 'Use only the tools you were given.'}
    args = t.coerce(call.input or {})
    blocked = check_gate(t, args, mem, ask, approval_mode)
    if blocked:
        trace.log(tool=call.name, args=args, result=blocked, error_class=blocked['error_class'], attempt=1)
        return blocked
    attempts = 3 if t.is_idempotent(args) else 1
    res = {}
    for i in range(attempts):
        t0 = time.time()
        cls = None
        try:
            res = {'ok': True, 'data': t.fn(**args)}
        except Exception as e:
            cls = classify(e)
            res = {'ok': False, 'error_class': cls, 'error': str(e)[:300], 'hint': HINTS.get(cls, '')}
        trace.log(tool=call.name, args=args, result=res, error_class=cls, attempt=i + 1,
                  ms=int((time.time() - t0) * 1000))
        if i > 0:
            trace.retries += 1
        if res['ok'] or cls not in RETRYABLE:
            break
        time.sleep(RETRY_BASE * 2 ** i)
    return res


def _evidence_files(run_dir):
    d = Path(run_dir)
    shots = sorted(d.glob('shot_*.png'))
    docs = sorted(p for p in d.iterdir() if p.suffix.lower() in ('.pdf', '.csv', '.txt'))
    return [str(p) for p in shots[-3:] + docs]


def build_report(status, summary, mem, trace, run_dir, verdict=None, notes=None):
    verdict = verdict or {}
    rep = {
        'status': status,
        'summary': summary,
        'verification_passed': bool(verdict.get('pass')),
        'verified': [{'criterion': e['criterion'], 'match': e['match'],
                      'observed': str(e['observed'])[:300]} for e in verdict.get('evidence', [])],
        'verification_failures': verdict.get('failures', []),
        'weak_verification': verdict.get('weak_verification', True),
        'evidence': _evidence_files(run_dir),
        'facts': mem.facts_dict(),
        'steps': trace.step, 'tool_calls': trace.tool_calls, 'retries': trace.retries,
        'questions_asked': trace.questions, 'cost_usd': round(trace.cost_usd, 4),
        'tokens': {'in': trace.tokens_in, 'out': trace.tokens_out},
        'seconds': round(time.time() - trace.t0, 1), 'run_dir': str(run_dir),
        'notes': notes or [],
    }
    (Path(run_dir) / 'result.json').write_text(json.dumps(rep, indent=2, default=str))
    trace.log('result', result={k: rep[k] for k in ('status', 'summary', 'verification_passed')})
    return rep


def run(goal, llm=None, ask=None, run_dir=None, max_steps=40, max_cost=1.0, approval_mode='auto',
        on_event=None):
    if llm is None:
        from .llm import GeminiLLM
        llm = GeminiLLM()
    run_dir = Path(run_dir or config.ROOT / 'runs' / time.strftime('%Y%m%d-%H%M%S'))
    mem = Memory(goal)
    trace = Trace(run_dir, secrets=mem.secrets, on_event=on_event)

    CTX.reset()
    CTX.memory, CTX.run_dir = mem, str(run_dir)

    def counted_ask(question, options=None):
        trace.questions += 1
        trace.log('ask', question=question, options=options)
        answer = (ask or cli_ask)(question, options)
        trace.log('answer', answer=answer)
        return answer
    CTX.ask = counted_ask

    msgs = [{'role': 'user', 'content': goal}]
    seen, failed = collections.Counter(), collections.Counter()
    verify_rounds, nudges, notes = 0, 0, []
    try:
        for _ in range(max_steps):
            trace.step += 1
            try:
                resp = llm.create(system_prompt() + mem.render(), specs(), mem.compact(msgs))
            except Exception as e:   # auth, quota or network failure: stop cleanly with an honest report
                trace.log('note', text=f'LLM call failed: {e}'[:500])
                return build_report('blocked', f'The model API call failed: {str(e)[:300]}', mem, trace,
                                    run_dir, notes=notes)
            trace.add_cost(resp.usage)
            if trace.cost_usd > max_cost:
                return build_report('blocked', f'Cost budget of ${max_cost} exceeded.', mem, trace, run_dir,
                                    notes=notes)
            msgs.append({'role': 'assistant', 'content': resp.content, 'raw': getattr(resp, 'raw', None)})
            for b in resp.content:
                if b.type == 'text' and b.text and b.text.strip():
                    trace.log('note', text=b.text.strip()[:500])
            calls = [b for b in resp.content if b.type == 'tool_use']
            if not calls:
                nudges += 1
                if nudges > 3:
                    return build_report('blocked', 'The model stopped calling tools without finishing.', mem,
                                        trace, run_dir, notes=notes)
                msgs.append({'role': 'user', 'content': 'Continue with a tool call, or call finish.'})
                continue

            results = []
            for c in calls:
                trace.tool_calls += 1
                inp = c.input or {}
                sig = (c.name, json.dumps(inp, sort_keys=True, default=str))
                seen[sig] += 1
                if c.name == 'finish':
                    verdict = verify(mem, llm, trace)
                    claimed = inp.get('status', 'partial')
                    summary = inp.get('summary', '')
                    if claimed != 'done':
                        return build_report(claimed, summary, mem, trace, run_dir, verdict, notes)
                    if verdict['pass']:
                        return build_report('done', summary, mem, trace, run_dir, verdict, notes)
                    verify_rounds += 1
                    if verify_rounds > 2:
                        notes.append('Claimed done but independent verification kept failing.')
                        return build_report('partial', summary, mem, trace, run_dir, verdict, notes)
                    out = {'ok': False, 'error_class': 'verification_failed',
                           'failures': verdict['failures'], 'hint': HINTS['verification_failed']}
                elif (seen[sig] >= 3 and failed[sig] >= 2) or seen[sig] >= 6:
                    out = {'ok': False, 'error_class': 'loop_detected', 'hint': HINTS['loop_detected']}
                    trace.log(tool=c.name, args=inp, result=out, error_class='loop_detected', attempt=1)
                else:
                    out = execute(c, mem, trace, CTX.ask, approval_mode)
                    if not out.get('ok'):
                        failed[sig] += 1
                results.append({'type': 'tool_result', 'tool_use_id': c.id, 'name': c.name,
                                'content': json.dumps(out, default=str)[:8000]})
            msgs.append({'role': 'user', 'content': results})
        return build_report('blocked', 'Step budget exhausted.', mem, trace, run_dir, notes=notes)
    finally:
        if CTX.browser is not None:
            try:
                CTX.browser.close()
            except Exception:
                pass
