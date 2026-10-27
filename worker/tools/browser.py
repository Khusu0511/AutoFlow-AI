"""Browser tools. The browser itself is a Puppeteer (Node.js) service in browser/server.js;
this module is the Python HTTP client plus the model-facing tool functions."""
import os

import httpx

from .. import config
from ..context import CTX
from ..errors import BrowserError
from .base import obj, tool
from .guard import check_url


class Browser:
    def __init__(self, run_dir, base=None):
        self.base = (base or config.BROWSER_URL).rstrip('/')
        self._call('start', run_dir=os.path.abspath(run_dir))

    def _call(self, action, **body):
        try:
            r = httpx.post(f'{self.base}/{action}', json=body, timeout=45)
        except httpx.ConnectError:
            raise BrowserError('service_unavailable', f'Puppeteer service not reachable at {self.base}')
        if r.status_code == 422:
            j = r.json()
            raise BrowserError(j['error_class'], j['error'])
        r.raise_for_status()
        return r.json()

    def goto(self, url): return self._call('goto', url=url)
    def read(self): return self._call('read')
    def click(self, id): return self._call('click', id=id)
    def type(self, id, text): return self._call('type', id=id, text=text)
    def select(self, id, value): return self._call('select', id=id, value=value)
    def download(self, id): return self._call('download', id=id)
    def close(self): return self._call('close')


def get_browser():
    if CTX.browser is None:
        CTX.browser = Browser(CTX.run_dir)
    return CTX.browser


def present(snap):
    """Turn a raw snapshot into a compact, model-friendly observation."""
    CTX.last_snapshot = snap
    lines = []
    for e in snap.get('elements', []):
        kind = e['tag'] + (f"[{e['type']}]" if e.get('type') else '')
        s = f"{e['id']}: {kind} '{e.get('label', '')}'"
        if e.get('value'):
            s += f" value='{e['value']}'"
        if e.get('options'):
            s += f" options={e['options']}"
        if e.get('href'):
            s += f" -> {e['href']}"
        if e.get('disabled'):
            s += ' (disabled)'
        lines.append(s)
    return {'url': snap['url'], 'title': snap['title'], 'page_text': snap['text'][:1800],
            'elements': lines, 'screenshot': snap.get('screenshot')}


@tool('browser_goto', 'Open a URL in the browser (company systems only). Returns the page text and a numbered '
      'list of interactive elements.', obj({'url': {'type': 'string'}}))
def browser_goto(url):
    check_url(url)
    return present(get_browser().goto(url))


@tool('browser_read', 'Re-read the current page: text plus freshly numbered interactive elements. '
      'Use after any surprise, and before clicking if ids may be stale.', obj({}))
def browser_read():
    return present(get_browser().read())


@tool('browser_click', 'Click an element by its id from the latest snapshot.',
      obj({'id': {'type': 'integer'}}), risk='write', idempotent=False)
def browser_click(id):
    return present(get_browser().click(id))


@tool('browser_type', 'Type text into an input/textarea by id (replaces existing text).',
      obj({'id': {'type': 'integer'}, 'text': {'type': 'string'}}), risk='write', idempotent=False,
      ground=lambda a: [a.get('text')] if not _is_password_field(a.get('id')) else [])
def browser_type(id, text):
    return present(get_browser().type(id, text))


@tool('browser_select', 'Choose an option in a <select> by its visible text or value.',
      obj({'id': {'type': 'integer'}, 'value': {'type': 'string'}}), risk='write', idempotent=False,
      ground=lambda a: [a.get('value')])
def browser_select(id, value):
    return present(get_browser().select(id, value))


@tool('browser_download', 'Download the file behind a link element (for example an invoice PDF) into the run '
      'folder. Returns the local path to pass to read_pdf.', obj({'id': {'type': 'integer'}}))
def browser_download(id):
    return get_browser().download(id)


def _is_password_field(el_id):
    """Typing into a password field is exempt from grounding: the secret came from get_credentials."""
    snap = CTX.last_snapshot or {}
    for e in snap.get('elements', []):
        if str(e.get('id')) == str(el_id):
            return e.get('type') == 'password'
    return False
