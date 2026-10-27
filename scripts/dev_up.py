"""Start Vendor Portal (:8001), FinanceDesk (:8002) and the Puppeteer service (:4000); Ctrl-C stops all.

  python scripts/dev_up.py            seed files if missing, then start everything
  python scripts/dev_up.py --reseed   regenerate PDFs/data and reset the MySQL tables first
Requires MySQL running with the credentials in .env (see README; `docker compose up -d mysql` is easiest).
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from worker import config  # noqa: E402

procs = []


def wait_health(name, url, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urlopen(url, timeout=2)
            print(f'  {name:<14} up   {url}')
            return
        except Exception:
            time.sleep(0.5)
    sys.exit(f'{name} did not become healthy at {url}; see runs/logs/{name}.log')


def start(name, cmd, cwd=ROOT):
    logs = ROOT / 'runs' / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    f = open(logs / f'{name}.log', 'w')
    procs.append(subprocess.Popen(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, env=os.environ.copy(),
                                  start_new_session=True))


def stop(*_):
    for p in procs:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    from env import seed
    import mysql.connector
    if '--reseed' in sys.argv or not (seed.DATA / 'vendors.json').exists():
        print('seeding data and database ...')
        seed.seed_files()
        try:
            seed.seed_db()
        except mysql.connector.Error as e:
            db = config.DB
            sys.exit(f"\nCannot reach MySQL at {db['host']}:{db['port']} as '{db['user']}' ({e}).\n"
                     'Start it with `docker compose up -d mysql` (wait until healthy) or fix DB_* in .env, '
                     'then run this again.')
    else:
        try:
            seed.db.init_schema()      # make sure the tables exist
        except mysql.connector.Error as e:
            sys.exit(f'Cannot reach MySQL ({e}). Start it with `docker compose up -d mysql` or fix DB_* in .env.')
    if not (ROOT / 'browser' / 'node_modules').exists():
        sys.exit('Run `cd browser && npm install` first.')
    py = sys.executable
    print('starting services ...')
    start('vendor_portal', [py, '-m', 'uvicorn', 'env.vendor_portal.app:app', '--port', '8001'])
    start('financedesk', [py, '-m', 'uvicorn', 'env.financedesk.app:app', '--port', '8002'])
    start('browser', ['node', 'server.js'], cwd=ROOT / 'browser')
    wait_health('vendor_portal', config.VENDOR_URL + '/health')
    wait_health('financedesk', config.FINANCEDESK_URL + '/health')
    wait_health('browser', config.BROWSER_URL + '/health')
    print('\nAll services are up. Run a task in another terminal, e.g.\n'
          "  python -m worker.cli 'Find the latest invoice from Acme Supplies and enter it in FinanceDesk'\n"
          'Ctrl-C here stops the services.')
    while True:
        time.sleep(1)
        for p in procs:
            if p.poll() is not None:
                print('a service exited unexpectedly; see runs/logs/')
                stop()


if __name__ == '__main__':
    main()
