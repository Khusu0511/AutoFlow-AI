"""Fault injection for FinanceDesk. FAULTS env var or POST /_admin/faults, e.g.
   err500=0.3,rename_btn,expire_after=4,slow=2
  err500=P      API calls fail with HTTP 500 with probability P
  slow=S        API calls take S extra seconds
  expire_after=N  the Nth API call finds the session expired (401); the agent must log in again
  rename_btn    the web form's submit button is renamed from 'Save Payable' to 'Submit'
"""
import asyncio
import os
import random

from fastapi.responses import JSONResponse


def parse(s):
    out = {}
    for part in filter(None, (s or '').split(',')):
        k, _, v = part.strip().partition('=')
        out[k] = float(v) if v else True
    return out


STATE = {'faults': parse(os.environ.get('FAULTS', '')), 'calls': 0}


def set_faults(spec):
    STATE['faults'] = parse(spec)
    STATE['calls'] = 0


def button_label():
    return 'Submit' if STATE['faults'].get('rename_btn') else 'Save Payable'


def install(app, sessions):
    @app.middleware('http')
    async def inject_faults(request, call_next):
        path = request.url.path
        if path.startswith('/api'):
            f = STATE['faults']
            if f.get('slow'):
                await asyncio.sleep(f['slow'])
            if random.random() < f.get('err500', 0):
                return JSONResponse({'detail': 'injected failure'}, status_code=500)
            if not path.endswith('/api/login'):
                STATE['calls'] += 1
                n = f.get('expire_after')
                if n and STATE['calls'] == int(n):
                    sessions.clear()
                    return JSONResponse({'detail': 'session expired'}, status_code=401)
        return await call_next(request)
