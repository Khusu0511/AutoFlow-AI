"""Scripted stand-in for the model, used ONLY for `--mock` runs and integration tests.

It exercises the real stack (browser service, PDFs, OCR, MySQL, gate, verifier, retries) without any LLM,
so the plumbing can be demonstrated and tested offline. It is an oracle for one task shape
('latest invoice from <vendor> -> enter in FinanceDesk'); it is NOT evidence of autonomy. The real run
uses GeminiLLM, which has to work all of this out itself.
"""
import calendar
import json
import re

from . import config

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
EL = re.compile(r"^(\d+): (\w+)(?:\[(\w+)\])? '(.*?)'(?: value='.*?')?(?: options=\[.*?\])?(?: -> (\S+))?")


def parse_elements(lines):
    out = []
    for ln in lines:
        m = EL.match(ln)
        if m:
            out.append({'id': int(m.group(1)), 'tag': m.group(2), 'type': m.group(3) or '',
                        'label': m.group(4), 'href': m.group(5) or ''})
    return out


def find(elements, label=None, type_=None, href_has=None):
    for e in elements:
        if label and label.lower() not in e['label'].lower():
            continue
        if type_ and e['type'] != type_:
            continue
        if href_has and href_has not in e['href']:
            continue
        return e
    raise LookupError(f'element not found: label={label} type={type_} href~{href_has}')


def to_iso(text):
    text = text.strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
        return text
    m = re.fullmatch(r'(\d{1,2}) ([A-Za-z]+) (\d{4})', text)
    if m:
        return f'{int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}'
    raise ValueError(f'cannot parse date {text!r}')


def call(name, inp):
    """Yield one tool call and return its single result."""
    res = yield (name, inp)
    return res[0]


def fd_login():
    creds = (yield from call('get_credentials', {'system': 'financedesk'}))['data']
    return (yield from call('http_post', {'url': f'{config.FINANCEDESK_URL}/api/login',
                                          'body': json.dumps({'username': creds['username'],
                                                              'password': creds['password']})}))


def fd_get(url):
    """GET with automatic re-login when the session expired."""
    for _ in range(3):
        res = yield from call('http_get', {'url': url})
        if res['ok']:
            return res['data']['body']
        if res.get('error_class') == 'session_expired':
            yield from fd_login()
            continue
        if res.get('error_class') in ('server_error', 'timeout'):
            continue
        raise RuntimeError(f'GET failed: {res}')
    raise RuntimeError('GET kept failing')


def web_login(system, url, user_label, submit_label='Sign in'):
    creds = (yield from call('get_credentials', {'system': system}))['data']
    snap = (yield from call('browser_goto', {'url': url}))['data']
    els = parse_elements(snap['elements'])
    yield from call('browser_type', {'id': find(els, user_label)['id'], 'text': creds['username']})
    yield from call('browser_type', {'id': find(els, type_='password')['id'], 'text': creds['password']})
    return (yield from call('browser_click', {'id': find(els, submit_label)['id']}))


def flagship_policy(goal):
    m = re.search(r'from (?:the )?([A-Z][A-Za-z ]+?)(?: and| to|,|\.|$)', goal)
    vendor = m.group(1).strip() if m else 'Acme Supplies'
    fd = config.FINANCEDESK_URL
    vp = config.VENDOR_URL

    yield from call('set_plan', {
        'subgoals': ['Log in to the Vendor Portal', f'Find the latest {vendor} invoice and read its PDF',
                     'Enter the payable in FinanceDesk', 'Verify the stored record'],
        'criteria': [{'description': f'FinanceDesk has a payable for {vendor}', 'tool': 'http_get',
                      'args_json': json.dumps({'url': f'{fd}/api/payables?vendor={vendor}'})}]})

    # 1. Vendor Portal: find the vendor's invoices
    yield from web_login('vendor_portal', f'{vp}/login', 'Email')
    page = (yield from call('browser_goto', {'url': f'{vp}/vendors'}))['data']
    names = [ln.split('\t')[0] for ln in page['page_text'].splitlines() if 'View invoices' in ln]
    links = [e for e in parse_elements(page['elements']) if e['label'] == 'View invoices']
    href = links[names.index(vendor)]['href']

    # 2. page through all invoices, keep the newest
    rows, url = [], vp + href
    while url:
        page = (yield from call('browser_goto', {'url': url}))['data']
        for ln in page['page_text'].splitlines():
            cells = ln.split('\t')
            if len(cells) >= 3 and cells[0].startswith('INV-'):
                rows.append((cells[1], cells[0], url))
        nxt = [e for e in parse_elements(page['elements']) if e['label'] == 'Next page']
        url = vp + nxt[0]['href'] if nxt else None
    newest = max(r[0] for r in rows)
    latest = [r for r in rows if r[0] == newest]
    if len(latest) > 1:
        answer = yield from call('ask_user', {'question': f'{len(latest)} {vendor} invoices share the latest date '
                                              f'{newest}. Which one?', 'options': [r[1] for r in latest]})
        chosen = next(r for r in latest if r[1] == answer['data']['answer'])
    else:
        chosen = latest[0]

    # 3. download and read the PDF
    page = (yield from call('browser_goto', {'url': chosen[2]}))['data']
    dl = find(parse_elements(page['elements']), f'Download PDF {chosen[1]}')
    path = (yield from call('browser_download', {'id': dl['id']}))['data']['path']
    doc = (yield from call('read_pdf', {'path': path}))['data']
    text = doc['document_text']
    inv_no = re.search(r'Invoice No:\s*(\S+)', text).group(1)
    amount = re.search(r'Amount Due:\s*([\d,]+\.\d\d)', text).group(1)
    due = to_iso(re.search(r'Due Date:\s*(.+)', text).group(1))
    conf = doc['ocr_confidence'] if doc['method'] == 'ocr' else 0.95
    src = f'{chosen[1]} PDF ({doc["method"]})'
    for k, v in (('vendor', vendor), ('invoice_no', inv_no), ('amount_due', amount), ('due_date', due)):
        yield from call('remember', {'key': k, 'value': v, 'source': src, 'confidence': conf})

    # 4. replan with exact, checkable criteria
    cents = int(round(float(amount.replace(',', '')) * 100))
    yield from call('set_plan', {
        'subgoals': ['Check FinanceDesk for an existing record', 'Enter the payable through the web form',
                     'Verify the stored record'],
        'criteria': [
            {'description': 'Stored amount equals the invoice amount due', 'tool': 'http_get',
             'args_json': json.dumps({'url': f'{fd}/api/payables?invoice_no={inv_no}'}),
             'expect_path': 'body.0.amount_cents', 'expect_equals': str(cents)},
            {'description': 'Stored due date equals the invoice due date', 'tool': 'http_get',
             'args_json': json.dumps({'url': f'{fd}/api/payables?invoice_no={inv_no}'}),
             'expect_path': 'body.0.due_date', 'expect_equals': due}]})

    # 5. already entered?
    yield from fd_login()
    existing = yield from fd_get(f'{fd}/api/payables?invoice_no={inv_no}')
    if existing:
        yield ('finish', {'status': 'done', 'summary': f'{inv_no} was already in FinanceDesk; nothing to enter.'})
        return

    # 6. enter it through the web UI
    yield from web_login('financedesk', f'{fd}/login', 'Username')
    page = (yield from call('browser_goto', {'url': f'{fd}/new'}))['data']
    els = parse_elements(page['elements'])
    for label, value in (('Vendor', vendor), ('Invoice number', inv_no), ('Amount', amount), ('Due date', due)):
        yield from call('browser_type', {'id': find(els, label)['id'], 'text': value})
    saved = yield from call('browser_click', {'id': find(els, type_='submit')['id']})
    ok_text = 'Saved payable' in (saved.get('data') or {}).get('page_text', '')

    # 7. finish; if verification bounces (for example the session expired), log in again and retry
    res = yield ('finish', {'status': 'done' if ok_text else 'partial',
                            'summary': f'Entered {inv_no} for {vendor}: amount due {amount}, due {due}.'})
    for _ in range(2):
        if res and res[0].get('error_class') == 'verification_failed':
            yield from fd_login()
            res = yield ('finish', {'status': 'done', 'summary': f'Entered {inv_no} for {vendor}: '
                                    f'amount due {amount}, due {due}.'})
