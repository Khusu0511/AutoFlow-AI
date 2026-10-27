"""HTTP tools for the company APIs. One cookie-keeping client per run so logins persist."""
import httpx

from ..context import CTX
from ..errors import HttpError
from .base import json_arg, obj, tool
from .guard import check_url

IDEMPOTENT_SUFFIXES = ('/api/login', '/api/payables', '/api/purchase_requests')


def client():
    if CTX.http is None:
        CTX.http = httpx.Client(timeout=15, follow_redirects=False)
    return CTX.http


def _parse(r):
    try:
        return r.json()
    except ValueError:
        return r.text[:3000]


def _result(r):
    body = _parse(r)
    if r.status_code >= 400:
        raise HttpError(r.status_code, body)
    return {'status': r.status_code, 'body': body}


@tool('http_get', 'GET a company API/page URL. Returns {status, body} (JSON parsed when possible).',
      obj({'url': {'type': 'string'}}))
def http_get(url):
    check_url(url)
    return _result(client().get(url))


def _post_risk(args):
    u = str(args.get('url', ''))
    return 'irreversible' if ('/mark_paid' in u or '/delete' in u) else 'write'


def _body(args):
    try:
        b = json_arg(args.get('body'), 'body')
    except Exception:
        return {}
    return b if isinstance(b, dict) else {}


def _post_idempotent(args):
    u = str(args.get('url', '')).split('?')[0]
    return u.endswith(IDEMPOTENT_SUFFIXES) or 'idempotency_key' in _body(args)


def _post_ground(args):
    if str(args.get('url', '')).endswith('/api/login'):
        return []
    body = _body(args)
    return [v for k, v in body.items() if k != 'idempotency_key' and isinstance(v, (str, int, float))
            and not isinstance(v, bool)]


@tool('http_post', 'POST JSON to a company API URL. Writes data, so every value must come from the task or a '
      'remembered fact. Returns {status, body}.',
      obj({'url': {'type': 'string'},
           'body': {'type': 'string', 'description': 'The JSON object to send, as a string, '
                    'e.g. \'{"invoice_no": "INV-1", "amount": 10.5}\''}}),
      risk=_post_risk, idempotent=_post_idempotent, ground=_post_ground)
def http_post(url, body):
    check_url(url)
    return _result(client().post(url, json=json_arg(body, 'body')))
