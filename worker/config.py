"""Central configuration. Everything comes from environment variables (.env is loaded if present)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv():
    env_file = ROOT / '.env'
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()


def env(name, default=''):
    return os.environ.get(name, default)


_key = env('GEMINI_API_KEY') or env('GOOGLE_API_KEY')
GEMINI_API_KEY = '' if _key.startswith('your-') else _key   # the .env.example placeholder counts as unset
MODEL = env('WORKER_MODEL', 'gemini-3.5-flash')
# USD per million tokens (thinking tokens count as output); used only for the cost cap
PRICE_IN = float(env('PRICE_IN_PER_MTOK', '1.5'))
PRICE_OUT = float(env('PRICE_OUT_PER_MTOK', '9'))

VENDOR_URL = env('VENDOR_URL', 'http://localhost:8001').rstrip('/')
FINANCEDESK_URL = env('FINANCEDESK_URL', 'http://localhost:8002').rstrip('/')
BROWSER_URL = env('BROWSER_URL', 'http://localhost:4000').rstrip('/')

DB = dict(
    host=env('DB_HOST', '127.0.0.1'),
    port=int(env('DB_PORT', '3306')),
    user=env('DB_USER', 'root'),
    password=env('DB_PASSWORD', 'root'),
    database=env('DB_NAME', 'financedesk'),
)

CREDENTIALS = {
    'vendor_portal': (env('VENDOR_USER', 'ap@company.test'), env('VENDOR_PASSWORD', 'vendor-pass')),
    'financedesk': (env('FINANCEDESK_USER', 'clerk'), env('FINANCEDESK_PASSWORD', 'desk-pass')),
}
