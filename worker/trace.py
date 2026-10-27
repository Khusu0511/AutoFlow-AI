"""JSONL trace of every step. Drives the UI, the demo and debugging. Secrets are redacted."""
import json
import time
from pathlib import Path

from . import config


class Trace:
    def __init__(self, run_dir, secrets=None, on_event=None):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.run_dir / 'trace.jsonl'
        self.secrets = secrets if secrets is not None else set()
        self.on_event = on_event
        self.step = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.cost_usd = 0.0
        self.retries = 0
        self.tool_calls = 0
        self.questions = 0
        self.t0 = time.time()

    def add_cost(self, usage):
        i = getattr(usage, 'input_tokens', 0) or 0
        o = getattr(usage, 'output_tokens', 0) or 0
        self.tokens_in += i
        self.tokens_out += o
        self.cost_usd = (self.tokens_in * config.PRICE_IN + self.tokens_out * config.PRICE_OUT) / 1e6

    def log(self, kind='tool', **kw):
        entry = {'ts': round(time.time() - self.t0, 2), 'step': self.step, 'kind': kind,
                 'cost_usd': round(self.cost_usd, 4), **kw}
        line = json.dumps(entry, default=str)
        for s in self.secrets:
            if s:
                line = line.replace(s, '***')
        if len(line) > 4000:   # keep traces readable
            entry['result'] = str(entry.get('result'))[:1500] + '...[truncated]'
            line = json.dumps(entry, default=str)
            for s in self.secrets:
                if s:
                    line = line.replace(s, '***')
        with open(self.path, 'a') as f:
            f.write(line + '\n')
        if self.on_event:
            self.on_event(json.loads(line))
