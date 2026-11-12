"""V25: all levels default to 10000; any positive stake editable without touching stored peers."""
import importlib
import os
import json
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient


def test_defaults_unlimited_levels_and_preserve_existing_stakes():
    with tempfile.TemporaryDirectory() as td:
        os.environ.update({
            'DATABASE_URL': 'sqlite:///' + str(Path(td) / 'v25.db'),
            'SECURE_COOKIE': '0',
            'SESSION_SECRET': 'v25-tests-with-safe-long-session-key',
        })
        import app
        os.environ['ADMIN_USERS_JSON'] = json.dumps({'admin01': app.hash_pw('TEST-secret-admin')})
        os.environ['VIEWER_PASSWORD_HASH'] = app.hash_pw('TEST-secret-viewer')
        importlib.reload(app)
        try:
            with TestClient(app.app) as c:
                login = c.post('/api/login', json={'role': 'admin', 'username': 'admin01', 'password': 'TEST-secret-admin'})
                assert login.status_code == 200, login.text
                headers = {'X-CSRF-Token': login.json()['csrf']}
                parent = None
                expected = {}
                for idx, stake in enumerate([None, '5000', '2345.67', '12345', '88888.88', '10000'], start=1):
                    account = f'L{idx}'
                    payload = {'account': account, 'joined_on': '2026-11-06', 'parent_account': parent}
                    if stake is not None:
                        payload['stake'] = stake
                    created = c.post('/api/members', headers=headers, json=payload)
                    assert created.status_code == 200, created.text
                    expected[account] = int(round(float(stake or '10000') * 100))
                    parent = account
                current = {r['account']: r for r in c.get('/api/tree').json()['members']}
                assert {account: current[account]['stake_cents'] for account in expected} == expected
                # Editing an existing third-level member to a nonstandard stake is supported.
                l3 = current['L3']
                updated = c.put('/api/members/' + l3['id'], headers=headers,
                    json={'account': 'L3', 'joined_on': l3['joined_on'], 'parent_account': 'L2',
                          'stake': '22222.22', 'total_withdraw': '0', 'expected_revision': l3['revision']})
                assert updated.status_code == 200, updated.text
                current = {r['account']: r for r in c.get('/api/tree').json()['members']}
                assert current['L3']['stake_cents'] == 2222222
                assert current['L1']['stake_cents'] == 1000000
                assert current['L2']['stake_cents'] == 500000
                assert current['L1']['subtree_stake_cents'] == sum(
                    r['stake_cents'] for r in current.values()
                )
                # A zero/negative stake remains invalid, independent of level.
                for bad in ['0', '-1']:
                    reject = c.post('/api/members', headers=headers,
                        json={'account': 'Invalid' + bad.replace('-', 'N'),
                              'joined_on': '2026-11-06', 'parent_account': 'L6', 'stake': bad})
                    assert reject.status_code == 400
                assert len(c.get('/api/tree').json()['members']) == 6
        finally:
            for k in ['ADMIN_USERS_JSON','VIEWER_PASSWORD_HASH']:
                os.environ.pop(k, None)
