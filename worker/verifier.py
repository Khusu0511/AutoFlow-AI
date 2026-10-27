"""Independent verification. Runs the plan's read-only checks against the live systems, then asks a judge
that sees only goal + facts + observed evidence (never the worker's chat history)."""
from .errors import classify
from .memory import same_value
from .tools.base import REGISTRY


def dig(obj, path):
    cur = obj
    for part in str(path).split('.'):
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur[part]
        else:
            raise KeyError(part)
    return cur


def deterministic_match(observed, expect):
    """True/False when an exact expectation exists, None when the criterion is left to the judge."""
    if not expect or 'equals' not in expect:
        return None
    try:
        got = dig(observed, expect['path']) if expect.get('path') else observed
    except (KeyError, IndexError, ValueError, TypeError):
        return False
    return same_value(got, expect['equals'])


def verify(mem, llm, trace=None):
    evidence = []
    for c in mem.criteria:
        chk = c.get('check', {})
        t = REGISTRY.get(chk.get('tool'))
        if t is None or t.risk_for(chk.get('args', {})) != 'read':
            evidence.append({'criterion': c.get('description'), 'observed': 'invalid check', 'match': False})
            continue
        try:
            observed = t.fn(**chk.get('args', {}))
        except Exception as e:   # a failing check is evidence too
            observed = {'error': f'{classify(e)}: {e}'}
            evidence.append({'criterion': c.get('description'), 'observed': observed, 'match': False})
            continue
        evidence.append({'criterion': c.get('description'), 'observed': observed,
                         'match': deterministic_match(observed, c.get('expect'))})

    payload = {'goal': mem.goal, 'facts': mem.facts_dict(), 'evidence': evidence}
    judge_note = None
    try:
        verdict = llm.judge(payload)
        judge_pass, failures = bool(verdict.get('pass')), list(verdict.get('failures', []))
    except Exception as e:   # judge unavailable: fall back to deterministic checks only, and say so
        judge_pass, failures, judge_note = True, [], f'judge unavailable ({e}); deterministic checks only'

    for e in evidence:
        if e['match'] is False:
            failures.append(f"check failed: {e['criterion']}")
    passed = judge_pass and all(e['match'] is not False for e in evidence)
    weak = not any(e['match'] is not None for e in evidence)
    result = {'pass': passed, 'failures': failures, 'evidence': evidence,
              'live_checks': len(evidence), 'exact_checks': sum(e['match'] is not None for e in evidence),
              'weak_verification': weak, 'judge_note': judge_note}
    if trace:
        trace.log('verify', result={k: result[k] for k in ('pass', 'failures', 'live_checks', 'exact_checks')})
    return result
