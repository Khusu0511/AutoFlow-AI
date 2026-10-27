"""Per-run shared state that tools need (memory, ask callback, browser, http client).

A module-level singleton keeps tool signatures clean (tools take only model-visible args).
The prototype runs one task at a time, so this is deliberate; see README 'Known limitations'.
"""


class Ctx:
    def __init__(self):
        self.reset()

    def reset(self):
        self.memory = None
        self.ask = None
        self.run_dir = None
        self.browser = None
        self.http = None
        self.last_snapshot = None   # most recent browser snapshot (used by the gate to spot commit buttons)


CTX = Ctx()
