"""Vendor Portal: a fake supplier site with login, vendors, paginated invoices, PDFs and quotes.
Data comes from env/data/vendors.json (created by `python -m env.seed`).
Run: uvicorn env.vendor_portal.app:app --port 8001"""
import asyncio
import json
import secrets
from pathlib import Path
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from worker import config

HERE = Path(__file__).parent
DATA = HERE.parent / 'data'
PAGE_SIZE = 5
SLOW_VENDOR_ID = 2          # trap: this vendor's invoice list takes 2 seconds to load

app = FastAPI(title='Vendor Portal')
templates = Jinja2Templates(directory=str(HERE / 'templates'))
SESSIONS = set()


def load():
    return json.loads((DATA / 'vendors.json').read_text())['vendors']


def require_login(request: Request):
    if request.cookies.get('vp_session') not in SESSIONS:
        raise HTTPException(status_code=303, headers={'Location': '/login'})


@app.exception_handler(HTTPException)
async def _exc(request: Request, exc: HTTPException):
    if exc.status_code == 303:
        return RedirectResponse(exc.headers['Location'], status_code=303)
    return HTMLResponse(f'<h1>{exc.status_code}</h1><p>{exc.detail}</p>', status_code=exc.status_code)


@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, 'login.html', {'error': None})


@app.post('/login')
def login_submit(request: Request, email: str = Form(''), password: str = Form('')):
    user, pw = config.CREDENTIALS['vendor_portal']
    if email != user or password != pw:
        return templates.TemplateResponse(request, 'login.html', {'error': 'Invalid credentials'}, status_code=403)
    token = secrets.token_hex(16)
    SESSIONS.add(token)
    resp = RedirectResponse('/vendors', status_code=303)
    resp.set_cookie('vp_session', token, httponly=True)
    return resp


@app.get('/', response_class=HTMLResponse)
def home(_=Depends(require_login)):
    return RedirectResponse('/vendors', status_code=303)


@app.get('/vendors', response_class=HTMLResponse)
def vendors(request: Request, _=Depends(require_login)):
    return templates.TemplateResponse(request, 'vendors.html', {'vendors': load()})


def _vendor(vid):
    for v in load():
        if v['id'] == vid:
            return v
    raise HTTPException(status_code=404, detail='vendor not found')


@app.get('/vendors/{vid}/invoices', response_class=HTMLResponse)
async def invoices(request: Request, vid: int, page: int = 1, _=Depends(require_login)):
    if vid == SLOW_VENDOR_ID:
        await asyncio.sleep(2)
    v = _vendor(vid)
    invs = sorted(v['invoices'], key=lambda i: (i['date'], i['no']))      # oldest first: latest is on the last page
    pages = max(1, -(-len(invs) // PAGE_SIZE))
    page = min(max(page, 1), pages)
    chunk = invs[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
    return templates.TemplateResponse(request, 'invoices.html', {
        'vendor': v, 'invoices': chunk, 'page': page, 'pages': pages})


@app.get('/invoices/{iid}.pdf')
def invoice_pdf(iid: int, _=Depends(require_login)):
    for v in load():
        for i in v['invoices']:
            if i['id'] == iid:
                return FileResponse(DATA / 'pdfs' / i['pdf'], media_type='application/pdf',
                                    filename=f"{i['no']}.pdf")
    raise HTTPException(status_code=404, detail='invoice not found')


@app.get('/vendors/{vid}/quotes', response_class=HTMLResponse)
def quotes(request: Request, vid: int, item: Optional[str] = None, _=Depends(require_login)):
    v = _vendor(vid)
    q = [x for x in v.get('quotes', []) if not item or x['item'] == item]
    return templates.TemplateResponse(request, 'quotes.html', {'vendor': v, 'quotes': q})


@app.get('/health')
def health():
    return {'ok': True}
