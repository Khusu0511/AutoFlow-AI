"""MySQL access for FinanceDesk (shared by the app, the seed script and the eval harness)."""
import mysql.connector

from worker import config

TABLES = {
    'payables': """
        CREATE TABLE IF NOT EXISTS payables (
          id INT AUTO_INCREMENT PRIMARY KEY,
          vendor VARCHAR(120) NOT NULL,
          invoice_no VARCHAR(40) NOT NULL,
          amount_cents BIGINT NOT NULL,
          due_date DATE NOT NULL,
          status VARCHAR(20) NOT NULL DEFAULT 'pending',
          idempotency_key VARCHAR(80) UNIQUE,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
    'purchase_requests': """
        CREATE TABLE IF NOT EXISTS purchase_requests (
          id INT AUTO_INCREMENT PRIMARY KEY,
          vendor VARCHAR(120) NOT NULL,
          item VARCHAR(60) NOT NULL,
          unit_price_cents BIGINT NOT NULL,
          quantity INT NOT NULL DEFAULT 1,
          idempotency_key VARCHAR(160) UNIQUE,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
}


def conn():
    return mysql.connector.connect(**config.DB)


def init_schema():
    cfg = dict(config.DB)
    name = cfg.pop('database')
    c = mysql.connector.connect(**cfg)
    cur = c.cursor()
    cur.execute(f'CREATE DATABASE IF NOT EXISTS `{name}`')
    c.close()
    c = conn()
    cur = c.cursor()
    for ddl in TABLES.values():
        cur.execute(ddl)
    c.commit()
    c.close()


def reset():
    c = conn()
    cur = c.cursor()
    for t in TABLES:
        cur.execute(f'TRUNCATE TABLE {t}')
    c.commit()
    c.close()


def fetch_all(sql, params=()):
    c = conn()
    cur = c.cursor(dictionary=True)
    cur.execute(sql, params)
    rows = cur.fetchall()
    c.close()
    return rows
