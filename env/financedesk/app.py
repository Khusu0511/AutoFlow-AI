"""FinanceDesk: the 'internal system'. Web UI + JSON API on MySQL, with fault injection.
Run: uvicorn env.financedesk.app:app --port 8002"""
import secrets
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

import mysql.connector
from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from env import db
from env.financedesk import faults
from worker import config

app = FastAPI(title='FinanceDesk')
templates = Jinja2Templates(directory=str(Path(__file__).parent / 'templates'))
SESSIONS = {}
faults.install(app, SESSIONS)


@app.on_event('startup')
def _startup():
    db.init_schema()


# ---------------------------------------------------------------- auth
def api_user(fd_session: Optional[str] = Cookie(None)):
    if fd_session not in SESSIONS:
        raise HTTPException(status_code=401, detail='not logged in')
    return SESSIONS[fd_session]


class LoginIn(BaseModel):
    username: str
    password: str


def _new_session(resp, username):
    token = secrets.token_hex(16)
    SESSIONS[token] = username
    resp.set_cookie('fd_session', token, httponly=True)
    return resp


@app.post('/api/login')
def api_login(body: LoginIn):
    user, pw = config.CREDENTIALS['financedesk']
    if body.username != user or body.password != pw:
        raise HTTPException(status_code=403, detail='bad credentials')
    return _new_session(JSONResponse({'ok': True}), user)


@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, 'login.html', {'error': None})


@app.post('/login')
def login_submit(request: Request, username: str = Form(''), password: str = Form('')):
    user, pw = config.CREDENTIALS['financedesk']
    if username != user or password != pw:
        return templates.TemplateResponse(request, 'login.html', {'error': 'Invalid credentials'}, status_code=403)
    return _new_session(RedirectResponse('/payables', status_code=303), user)


def ui_user(request: Request):
    if request.cookies.get('fd_session') not in SESSIONS:
        raise HTTPException(status_code=303, headers={'Location': '/login'})


# ---------------------------------------------------------------- helpers
def _row(r):
    return {'id': r['id'], 'vendor': r['vendor'], 'invoice_no': r['invoice_no'],
            'amount_cents': r['amount_cents'], 'amount': r['amount_cents'] / 100,
            'due_date': r['due_date'].isoformat() if hasattr(r['due_date'], 'isoformat') else str(r['due_date']),
            'status': r['status']}


def insert_payable(vendor, invoice_no, amount, due, key):
    cents = int((Decimal(str(amount)) * 100).quantize(Decimal('1')))
    c = db.conn()
    cur = c.cursor()
    try:
        cur.execute('INSERT INTO payables (vendor, invoice_no, amount_cents, due_date, idempotency_key) '
                    'VALUES (%s, %s, %s, %s, %s)', (vendor, invoice_no, cents, due, key))
        c.commit()
        return cur.lastrowid
    finally:
        c.close()


# ---------------------------------------------------------------- JSON API
class PayableIn(BaseModel):
    vendor: str = Field(min_length=1)
    invoice_no: str = Field(min_length=1)
    amount: float = Field(gt=0)
    due_date: date
    idempotency_key: Optional[str] = None


@app.post('/api/payables', status_code=201)
def create_payable(p: PayableIn, user=Depends(api_user)):
    try:
        new_id = insert_payable(p.vendor, p.invoice_no, p.amount, p.due_date, p.idempotency_key or p.invoice_no)
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=409, detail='duplicate: this invoice was already entered')
    return {'id': new_id}


@app.get('/api/payables')
def list_payables(invoice_no: Optional[str] = None, vendor: Optional[str] = None, user=Depends(api_user)):
    sql, params = 'SELECT * FROM payables WHERE 1=1', []
    if invoice_no:
        sql += ' AND invoice_no = %s'
        params.append(invoice_no)
    if vendor:
        sql += ' AND vendor = %s'
        params.append(vendor)
    return [_row(r) for r in db.fetch_all(sql + ' ORDER BY id', tuple(params))]


@app.get('/api/payables/{pid}')
def get_payable(pid: int, user=Depends(api_user)):
    rows = db.fetch_all('SELECT * FROM payables WHERE id = %s', (pid,))
    if not rows:
        raise HTTPException(status_code=404, detail='not found')
    return _row(rows[0])


@app.post('/api/payables/{pid}/mark_paid')
def mark_paid(pid: int, user=Depends(api_user)):
    c = db.conn()
    cur = c.cursor()
    cur.execute("UPDATE payables SET status = 'paid' WHERE id = %s", (pid,))
    c.commit()
    c.close()
    return {'id': pid, 'status': 'paid'}


class PurchaseRequestIn(BaseModel):
    vendor: str = Field(min_length=1)
    item: str = Field(min_length=1)
    unit_price: float = Field(gt=0)
    quantity: int = Field(default=1, ge=1)
    idempotency_key: Optional[str] = None


@app.post('/api/purchase_requests', status_code=201)
def create_pr(p: PurchaseRequestIn, user=Depends(api_user)):
    cents = int((Decimal(str(p.unit_price)) * 100).quantize(Decimal('1')))
    c = db.conn()
    cur = c.cursor()
    try:
        cur.execute('INSERT INTO purchase_requests (vendor, item, unit_price_cents, quantity, idempotency_key) '
                    'VALUES (%s, %s, %s, %s, %s)',
                    (p.vendor, p.item, cents, p.quantity, p.idempotency_key or f'{p.vendor}:{p.item}'))
        c.commit()
        return {'id': cur.lastrowid}
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=409, detail='duplicate purchase request')
    finally:
        c.close()


@app.get('/api/purchase_requests')
def list_prs(user=Depends(api_user)):
    rows = db.fetch_all('SELECT * FROM purchase_requests ORDER BY id')
    return [{'id': r['id'], 'vendor': r['vendor'], 'item': r['item'],
             'unit_price': r['unit_price_cents'] / 100, 'quantity': r['quantity']} for r in rows]


# ---------------------------------------------------------------- web UI
@app.get('/', response_class=HTMLResponse)
def home(request: Request, _=Depends(ui_user)):
    return RedirectResponse('/payables', status_code=303)


@app.get('/new', response_class=HTMLResponse)
def new_form(request: Request, _=Depends(ui_user)):
    return templates.TemplateResponse(request, 'new.html', {'button_label': faults.button_label(), 'error': None})


@app.post('/new')
def new_submit(request: Request, vendor: str = Form(''), invoice_no: str = Form(''), amount: str = Form(''),
               due_date: str = Form(''), _=Depends(ui_user)):
    def fail(msg):
        return templates.TemplateResponse(request, 'new.html',
                                          {'button_label': faults.button_label(), 'error': msg}, status_code=422)
    if not vendor.strip() or not invoice_no.strip():
        return fail('Vendor and invoice number are required.')
    try:
        amt = Decimal(amount.replace(',', '').strip())
        if amt <= 0:
            raise InvalidOperation
    except InvalidOperation:
        return fail('Amount must be a positive decimal number, e.g. 4250.00')
    try:
        due = date.fromisoformat(due_date.strip())
    except ValueError:
        return fail('Due date must be in YYYY-MM-DD format.')
    try:
        insert_payable(vendor.strip(), invoice_no.strip(), amt, due, invoice_no.strip())
    except mysql.connector.IntegrityError:
        return fail('Duplicate: this invoice was already entered.')
    return RedirectResponse(f'/payables?saved={invoice_no.strip()}', status_code=303)


@app.get('/payables', response_class=HTMLResponse)
def payables_page(request: Request, saved: Optional[str] = None, _=Depends(ui_user)):
    rows = [_row(r) for r in db.fetch_all('SELECT * FROM payables ORDER BY id')]
    return templates.TemplateResponse(request, 'payables.html', {'rows': rows, 'saved': saved})


# ---------------------------------------------------------------- admin (test harness only)
@app.post('/_admin/reset')
def admin_reset():
    db.reset()
    SESSIONS.clear()
    faults.STATE['calls'] = 0
    return {'ok': True}


@app.post('/_admin/faults')
def admin_faults(body: dict):
    faults.set_faults(body.get('faults', ''))
    return {'ok': True, 'faults': faults.STATE['faults']}


@app.get('/health')
def health():
    return {'ok': True}


@app.exception_handler(HTTPException)
async def _http_exc(request: Request, exc: HTTPException):
    if exc.status_code == 303:
        return RedirectResponse(exc.headers['Location'], status_code=303)
    return JSONResponse({'detail': exc.detail}, status_code=exc.status_code)
