"""Run memory: facts with provenance, the current plan and success criteria, and history compaction."""
import json
import math
import re
from dataclasses import dataclass


@dataclass
class Fact:
    value: str
    source: str
    confidence: float


def norm(s):
    return re.sub(r'[\s,]+', '', str(s)).lower()


def _num(x):
    try:
        return float(str(x).replace(',', '').strip())
    except (TypeError, ValueError):
        return None


def same_value(a, b):
    """Tolerant equality: '4,250.00' == 4250 == '4250.0'; strings compare case/space-insensitively."""
    na, nb = _num(a), _num(b)
    if na is not None and nb is not None:
        return math.isclose(na, nb, abs_tol=1e-9)
    return norm(a) == norm(b)


SECRET_HINTS = ('password', 'secret', 'token')


class Memory:
    def __init__(self, goal):
        self.goal = goal
        self.facts = {}
        self.secrets = set()      # values that must never appear in traces or the prompt
        self.plan = []
        self.criteria = []

    # -- facts -------------------------------------------------------------
    def remember(self, key, value, source, confidence=0.9, secret=False):
        self.facts[key] = Fact(str(value), source, float(confidence))
        if secret or any(h in key.lower() for h in SECRET_HINTS):
            self.secrets.add(str(value))

    def matching_facts(self, value):
        return [(k, f) for k, f in self.facts.items() if same_value(f.value, value)]

    def grounded(self, value):
        """A written value must come from the task text or from a remembered fact."""
        if self.matching_facts(value):
            return True
        n = norm(value)
        return len(n) >= 2 and n in norm(self.goal)

    def _shown(self, k, f):
        return '***' if f.value in self.secrets else f.value

    def facts_dict(self):
        return {k: {'value': self._shown(k, f), 'source': f.source, 'confidence': f.confidence}
                for k, f in self.facts.items()}

    def render(self):
        lines = [f'- {k} = {self._shown(k, f)} (source: {f.source}, confidence {f.confidence})'
                 for k, f in self.facts.items()]
        plan = '; '.join(self.plan) if self.plan else '(not set yet: call set_plan)'
        return ('\n\nCURRENT PLAN: ' + plan +
                '\nKNOWN FACTS:\n' + ('\n'.join(lines) if lines else '(none yet)'))

    # -- history compaction -------------------------------------------------
    def compact(self, msgs, keep=16):
        """Return a copy of msgs where tool results older than the last `keep` messages are replaced by
        one-line summaries. Message structure (tool_use/tool_result pairing) is preserved."""
        out = []
        cutoff = len(msgs) - keep
        for i, m in enumerate(msgs):
            if 0 < i < cutoff and m['role'] == 'user' and isinstance(m['content'], list):
                out.append({'role': 'user', 'content': [self._summarize(b) for b in m['content']]})
            else:
                out.append(m)
        return out

    @staticmethod
    def _summarize(block):
        if not isinstance(block, dict) or block.get('type') != 'tool_result':
            return block
        text = block['content'] if isinstance(block['content'], str) else str(block['content'])
        try:
            d = json.loads(text)
            head = 'ok' if d.get('ok') else 'error:' + str(d.get('error_class'))
            body = json.dumps(d.get('data', d.get('error', '')))[:100]
            text = f'[earlier result] {head} {body}'
        except (ValueError, AttributeError):
            text = '[earlier result] ' + text[:100]
        return {**block, 'content': text}
