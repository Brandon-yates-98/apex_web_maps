"""
Apply campsite SQL migrations in batches via Supabase REST API.

Usage:
  ! op run --env-file=.env.tpl -- .venv/Scripts/python.exe scripts/apply_campsite_sql.py
"""
import os, sys, json, urllib.request, urllib.error

URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
KEY = os.environ.get('SUPABASE_KEY', '')

if not URL or not KEY:
    print('ERROR: SUPABASE_URL and SUPABASE_KEY must be set.')
    print('Run: op run --env-file=.env.tpl -- .venv/Scripts/python.exe scripts/apply_campsite_sql.py')
    sys.exit(1)

SQL_FILES = [
    'migrations/026a.sql',
    'migrations/026b.sql',
]

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

BATCH_SIZE = 30


def run_sql(sql: str, label: str):
    endpoint = f'{URL}/rest/v1/rpc/execute_sql'
    # Try PostgREST rpc endpoint first, fall back to pg endpoint
    body = json.dumps({'query': sql}).encode()
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            'apikey': KEY,
            'Authorization': f'Bearer {KEY}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f'  OK  {label}')
            return True
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        print(f'  ERR {label}: {e.code} {body_text[:200]}')
        return False


def run_sql_pg(sql: str, label: str):
    """Use the Supabase SQL over HTTP endpoint (service role only)."""
    endpoint = f'{URL}/pg/query'
    body = json.dumps({'query': sql}).encode()
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            'apikey': KEY,
            'Authorization': f'Bearer {KEY}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f'  OK  {label}')
            return True
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        print(f'  ERR {label}: {e.code} {body_text[:200]}')
        return False


def apply_file(path: str):
    full_path = os.path.join(_ROOT, path)
    print(f'\nReading {path}...')
    with open(full_path) as f:
        lines = [l.rstrip('\n') for l in f if l.strip()]

    # Execute DELETE/DDL lines individually, batch INSERTs
    inserts = []
    for line in lines:
        if line.lower().startswith('delete') or line.lower().startswith('--'):
            if inserts:
                flush_batch(inserts, path)
                inserts = []
            if line.startswith('--'):
                continue
            ok = run_sql_pg(line, f'DELETE in {path}')
            if not ok:
                print('Aborting.')
                sys.exit(1)
        else:
            inserts.append(line)
            if len(inserts) >= BATCH_SIZE:
                flush_batch(inserts, path)
                inserts = []
    if inserts:
        flush_batch(inserts, path)


_batch_num = 0

def flush_batch(inserts: list, path: str):
    global _batch_num
    _batch_num += 1
    sql = '\n'.join(inserts)
    label = f'batch {_batch_num} ({len(inserts)} rows) from {os.path.basename(path)}'
    ok = run_sql_pg(sql, label)
    if not ok:
        print('Aborting.')
        sys.exit(1)
    inserts.clear()


for f in SQL_FILES:
    apply_file(f)

print('\nDone.')
