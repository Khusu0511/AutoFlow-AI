"""Safety gate: runs before every non-read tool call.

1. A plan must exist.
2. Grounding: every value the tool will write must trace to the task text or a remembered fact.
3. Approval: the user is asked for irreversible actions, for values with low-confidence provenance,
   and (optionally) before commit-style actions.
"""
import re

from .context import CTX

LOW_CONFIDENCE = 0.8
COMMIT_RE = re.compile(r'\b(save|submit|confirm|pay|delete|approve|send|create)\b', re.I)
APPROVE = {'approve', 'approved', 'yes', 'y', 'ok'}


def _err(cls, hint, **extra):
    return {'ok': False, 'error_class': cls, 'hint': hint, **extra}


def is_commit(tool, args):
    if tool.name == 'http_post':
        return not str(args.get('url', '')).endswith('/api/login')
    if tool.name == 'browser_click' and CTX.last_snapshot:
        for el in CTX.last_snapshot.get('elements', []):
            if str(el.get('id')) == str(args.get('id')):
                return bool(COMMIT_RE.search(el.get('label', '') or ''))
    return False


def check_gate(tool, args, mem, ask, approval_mode='auto'):
    from .errors import HINTS
    risk = tool.risk_for(args)
    if risk == 'read':
        return None
    if not mem.plan:
        return _err('no_plan', HINTS['no_plan'])

    values = tool.values_to_ground(args)
    ungrounded = [v for v in values if not mem.grounded(v)]
    if ungrounded:
        return _err('ungrounded_args', HINTS['ungrounded_args'], values=[str(v) for v in ungrounded])

    low = sorted({k for v in values for k, f in mem.matching_facts(v) if f.confidence < LOW_CONFIDENCE})
    reasons = []
    if risk == 'irreversible':
        reasons.append('this action is irreversible')
    if low:
        reasons.append('low-confidence facts used: ' + ', '.join(low))
    if approval_mode == 'all':
        reasons.append('approve-all mode')
    elif approval_mode == 'writes' and is_commit(tool, args):
        reasons.append('this action commits data')

    if reasons:
        shown = {k: ('***' if str(v) in mem.secrets else v) for k, v in args.items()}
        answer = ask(f'Approve {tool.name} {shown}? Reason: {"; ".join(reasons)}.', ['approve', 'deny'])
        if str(answer).strip().lower() not in APPROVE:
            return _err('user_denied', HINTS['user_denied'])
    return None
