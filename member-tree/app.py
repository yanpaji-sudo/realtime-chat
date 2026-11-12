"""内部会员树状统计系统：服务端共享数据 + 双角色权限 + 批量导入。"""
import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import monotonic, sleep

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parent
DB_URL = os.environ.get('DATABASE_URL', 'sqlite:///' + str(ROOT / 'local-demo.db'))
if DB_URL.startswith('postgres://'):
    DB_URL = 'postgresql+psycopg://' + DB_URL[len('postgres://'):]
elif DB_URL.startswith('postgresql://'):
    DB_URL = DB_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
engine = create_engine(DB_URL, pool_pre_ping=True, connect_args={'check_same_thread': False} if DB_URL.startswith('sqlite:') else {})
SESSION_SECRET = os.environ.get('SESSION_SECRET', '')
ADMIN_HASH = os.environ.get('ADMIN_PASSWORD_HASH', '')
# Optional single-account password rotation without modifying any other admin credentials.
ADMIN04_PASSWORD_HASH = os.environ.get('ADMIN04_PASSWORD_HASH', '')
VIEWER_HASH = os.environ.get('VIEWER_PASSWORD_HASH', '')
try:
    ADMIN_USERS = json.loads(os.environ.get('ADMIN_USERS_JSON', '{}'))
    if not isinstance(ADMIN_USERS, dict): ADMIN_USERS = {}
except (ValueError, TypeError):
    ADMIN_USERS = {}
COOKIE = 'liuxing_member_tree_test_session'
serializer = URLSafeTimedSerializer(SESSION_SECRET or 'UNCONFIGURED', salt='liuxing-member-tree-test')
SESSION_AGE = 8 * 3600
RATE = {}
RATE_LOCK = threading.Lock()
app = FastAPI(title='流星会员树状统计系统（独立测试版）', docs_url=None, redoc_url=None, openapi_url=None)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def current_day():
    return datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()


def set_daily_ledger(db, member_id, day, amount):
    if not day: return
    old=db.execute(text('SELECT amount_cents FROM daily_withdraw_ledger WHERE member_id=:m AND business_day=:d'),
                   {'m':member_id,'d':day}).first()
    if int(amount)==0:
        if old: db.execute(text('DELETE FROM daily_withdraw_ledger WHERE member_id=:m AND business_day=:d'),
                           {'m':member_id,'d':day})
    elif old:
        db.execute(text('UPDATE daily_withdraw_ledger SET amount_cents=:a WHERE member_id=:m AND business_day=:d'),
                   {'m':member_id,'d':day,'a':int(amount)})
    else:
        db.execute(text('INSERT INTO daily_withdraw_ledger(member_id,business_day,amount_cents) VALUES (:m,:d,:a)'),
                   {'m':member_id,'d':day,'a':int(amount)})


def report_window(day):
    d=date.fromisoformat(day)
    return (d-timedelta(days=d.weekday())).isoformat(),d.replace(day=1).isoformat()


def settle_past_days(db, today=None):
    """Close historical recorded business days once, atomically and idempotently.

    On a sleeping free server this happens on the next wake-up, never falsely
    claims an exact 00:00 capture. The day's last observed snapshot is retained.
    """
    today=today or current_day()
    days=[x[0] for x in db.execute(text('''SELECT business_day FROM daily_group_snapshots WHERE business_day<:d
          UNION SELECT business_day FROM daily_withdraw_ledger WHERE business_day<:d
          UNION SELECT business_day FROM daily_withdraw_credit WHERE business_day<:d
          ORDER BY business_day'''),{'d':today}).all()]
    for day in days:
        if db.execute(text('SELECT 1 FROM daily_business_closes WHERE business_day=:d'),{'d':day}).first():
            continue
        # Include previously credited members whose FINAL daily upload is zero
        # (the zero amount is intentionally absent from the ledger).
        previous=db.execute(text('''SELECT member_id,credited_cents FROM daily_withdraw_credit
                  WHERE business_day=:d'''),{'d':day}).mappings().all()
        credited_by_member={x['member_id']:int(x['credited_cents']) for x in previous}
        final_by_member={x['member_id']:int(x['amount_cents']) for x in db.execute(text('''
                  SELECT member_id,amount_cents FROM daily_withdraw_ledger WHERE business_day=:d'''),
                  {'d':day}).mappings().all()}
        for member_id in set(credited_by_member)|set(final_by_member):
            credited=credited_by_member.get(member_id,0)
            final=final_by_member.get(member_id,0)
            delta=final-credited
            if delta:
                db.execute(text('''UPDATE members SET total_withdraw_cents=total_withdraw_cents+:delta,
                    revision=revision+1,updated_at=:now WHERE id=:i'''),
                    {'delta':delta,'i':member_id,'now':utc_now()})
            db.execute(text('''INSERT INTO daily_withdraw_credit
                     (member_id,business_day,credited_cents,settled_at)
                     VALUES (:i,:d,:v,:now)
                     ON CONFLICT(member_id,business_day) DO UPDATE SET
                     credited_cents=excluded.credited_cents,settled_at=excluded.settled_at'''),
                     {'i':member_id,'d':day,'v':final,'now':utc_now()})
        last=db.execute(text('''SELECT MAX(captured_at) FROM daily_group_snapshots
                 WHERE business_day=:d'''),{'d':day}).scalar()
        # A near-midnight capture is marked separately; only a persistent scheduler
        # on an always-on server can guarantee the boundary under suspension.
        quality='latest_observation' if last else 'withdrawals_only'
        if last:
            observed=datetime.fromisoformat(last).astimezone(ZoneInfo('Asia/Shanghai'))
            closing=datetime.combine(date.fromisoformat(day)+timedelta(days=1),datetime.min.time(),tzinfo=ZoneInfo('Asia/Shanghai'))
            if observed.date().isoformat()==day and timedelta(0)<closing-observed<=timedelta(seconds=60):
                quality='near_midnight'
        db.execute(text('''INSERT INTO daily_business_closes
             (business_day,closed_at,source_captured_at,quality)
             VALUES (:d,:now,:captured,:quality)'''),
             {'d':day,'now':utc_now(),'captured':last,'quality':quality})

def capture_current_report(db,day=None):
    day=day or current_day()
    store_live_report_snapshots(db,report_rows_today(db,day))

def db_init():
    with engine.begin() as db:
        db.execute(text('''CREATE TABLE IF NOT EXISTS members (
            id TEXT PRIMARY KEY, account TEXT NOT NULL UNIQUE, joined_on TEXT NOT NULL,
            parent_id TEXT NULL REFERENCES members(id), balance_cents BIGINT NOT NULL DEFAULT 0,
            total_withdraw_cents BIGINT NOT NULL DEFAULT 0,
            daily_withdraw_cents BIGINT NOT NULL DEFAULT 0,
            stake_cents BIGINT NOT NULL DEFAULT 0,
            daily_withdraw_on TEXT,
            remark TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 1,
            deleted INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)'''))
        from sqlalchemy import inspect
        columns = {c['name'] for c in inspect(db).get_columns('members')}
        if 'stake_cents' not in columns:
            db.execute(text('ALTER TABLE members ADD COLUMN stake_cents BIGINT NOT NULL DEFAULT 0'))
        if 'daily_withdraw_on' not in columns:
            db.execute(text('ALTER TABLE members ADD COLUMN daily_withdraw_on TEXT'))
            # Existing pre-upgrade daily values have no date. Preserve their visibility on upgrade day
            # without crediting them again to historical withdrawals.
            db.execute(text('UPDATE members SET daily_withdraw_on=:d WHERE daily_withdraw_cents>0 AND daily_withdraw_on IS NULL'), {'d': current_day()})
        if 'remark' not in columns:
            db.execute(text("ALTER TABLE members ADD COLUMN remark TEXT NOT NULL DEFAULT ''"))
        if 'revision' not in columns:
            db.execute(text('ALTER TABLE members ADD COLUMN revision INTEGER NOT NULL DEFAULT 1'))
        db.execute(text('CREATE INDEX IF NOT EXISTS idx_member_parent ON members(parent_id)'))
        db.execute(text('''CREATE TABLE IF NOT EXISTS legacy_restore_jobs (
            id TEXT PRIMARY KEY, rows_json TEXT NOT NULL,
            source_stamp TEXT NOT NULL, created_at TEXT NOT NULL)'''))
        db.execute(text('''CREATE TABLE IF NOT EXISTS import_jobs (
            id TEXT PRIMARY KEY, mode TEXT NOT NULL, rows_json TEXT NOT NULL,
            roster_stamp TEXT NOT NULL, created_at TEXT NOT NULL, applied INTEGER NOT NULL DEFAULT 0)'''))
        db.execute(text('''CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY, event TEXT NOT NULL, detail TEXT NOT NULL,
            created_at TEXT NOT NULL)'''))
        # Additive table for auditable cross-admin undo; does not modify existing member records.
        # Every reversible change and its pre/post snapshot is committed atomically.
        db.execute(text('''CREATE TABLE IF NOT EXISTS undo_actions (
            id TEXT PRIMARY KEY, operator TEXT NOT NULL, event TEXT NOT NULL,
            label TEXT NOT NULL, changes_json TEXT NOT NULL,
            created_at TEXT NOT NULL, undone INTEGER NOT NULL DEFAULT 0,
            undone_at TEXT)'''))
        db.execute(text('CREATE INDEX IF NOT EXISTS idx_undo_created ON undo_actions(created_at)'))
        # Additive tables: no existing member balances, dates or relationships changed.
        db.execute(text('''CREATE TABLE IF NOT EXISTS daily_withdraw_ledger (
            member_id TEXT NOT NULL,business_day TEXT NOT NULL,
            amount_cents BIGINT NOT NULL DEFAULT 0,
            PRIMARY KEY(member_id,business_day))'''))
        db.execute(text('''CREATE TABLE IF NOT EXISTS daily_import_days (
            business_day TEXT PRIMARY KEY,recorded_at TEXT NOT NULL)'''))
        # V20: record which per-day withdrawal snapshot was already included in the cumulative total.
        db.execute(text("""CREATE TABLE IF NOT EXISTS daily_withdraw_credit (
            member_id TEXT NOT NULL,business_day TEXT NOT NULL, credited_cents BIGINT NOT NULL,
            settled_at TEXT, PRIMARY KEY(member_id,business_day))"""))
        db.execute(text("""CREATE TABLE IF NOT EXISTS daily_business_closes (
            business_day TEXT PRIMARY KEY,closed_at TEXT NOT NULL,source_captured_at TEXT,
            quality TEXT NOT NULL)"""))
        db.execute(text('''CREATE TABLE IF NOT EXISTS daily_group_snapshots (
            business_day TEXT NOT NULL, group_account TEXT NOT NULL,
            member_count INTEGER NOT NULL, new_count INTEGER NOT NULL,
            new_stake_cents BIGINT NOT NULL, withdraw_cents BIGINT NOT NULL,
            balance_cents BIGINT NOT NULL, captured_at TEXT NOT NULL,
            PRIMARY KEY (business_day, group_account))'''))
        db.execute(text('CREATE INDEX IF NOT EXISTS idx_daily_group_snapshots_day ON daily_group_snapshots(business_day)'))
        db.execute(text("CREATE TABLE IF NOT EXISTS team_names (member_id TEXT PRIMARY KEY, name TEXT NOT NULL, updated_at TEXT NOT NULL)"))
        # V33: small, independent status log. Existing member/finance tables unchanged.
        db.execute(text("""CREATE TABLE IF NOT EXISTS position_alert_state (
            account TEXT PRIMARY KEY,opened_on TEXT NOT NULL,closed_on TEXT,
            active INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL)"""))
        db.execute(text("CREATE TABLE IF NOT EXISTS daily_member_fission (member_id TEXT NOT NULL,business_day TEXT NOT NULL,ratio_bp INTEGER NOT NULL,captured_at TEXT NOT NULL,PRIMARY KEY(member_id,business_day))"))
        db.execute(text('''CREATE TABLE IF NOT EXISTS reporting_meta (
            name TEXT PRIMARY KEY,value TEXT NOT NULL)'''))
        # Separate manual reporting corrections. They do not overwrite member finances
        # or immutable sampled values in daily_group_snapshots.
        db.execute(text('''CREATE TABLE IF NOT EXISTS report_manual_overrides (
            business_day TEXT NOT NULL,group_account TEXT NOT NULL,
            values_json TEXT NOT NULL,operator TEXT NOT NULL,updated_at TEXT NOT NULL,
            PRIMARY KEY(business_day,group_account))'''))
        # Old releases already credited every imported daily-withdrawal snapshot into total.
        # Migrate credits only ONCE to avoid double-counting previous imports on upgrade.
        if not db.execute(text("SELECT value FROM reporting_meta WHERE name='v20_withdraw_credit_migrated'")).first():
            for item in db.execute(text('SELECT member_id,business_day,amount_cents FROM daily_withdraw_ledger')).mappings():
                db.execute(text('''INSERT INTO daily_withdraw_credit(member_id,business_day,credited_cents,settled_at)
                   VALUES (:m,:d,:a,NULL) ON CONFLICT(member_id,business_day) DO NOTHING'''),
                   {'m':item['member_id'],'d':item['business_day'],'a':item['amount_cents']})
            db.execute(text("INSERT INTO reporting_meta(name,value) VALUES('v20_withdraw_credit_migrated','1')"))
        if not db.execute(text("SELECT value FROM reporting_meta WHERE name='tracking_since'")).first():
            db.execute(text("INSERT INTO reporting_meta(name,value) VALUES('tracking_since',:d)"),
                       {'d':current_day()})
            # Carry across the last known daily snapshot, not invented older history.
            for old in db.execute(text('''SELECT id,daily_withdraw_on,daily_withdraw_cents FROM members
                 WHERE deleted=0 AND daily_withdraw_on IS NOT NULL AND daily_withdraw_cents>0''')).mappings():
                set_daily_ledger(db,old['id'],old['daily_withdraw_on'],int(old['daily_withdraw_cents']))



def midnight_capture_worker():
    # Best effort when the instance stays awake. Free Render instance suspension
    # may stop the worker; the fallback remains the last recorded daily snapshot.
    while True:
        now=datetime.now(ZoneInfo('Asia/Shanghai'))
        boundary=datetime.combine(now.date()+timedelta(days=1),datetime.min.time(),tzinfo=ZoneInfo('Asia/Shanghai'))
        target=boundary-timedelta(milliseconds=300)
        until=(target-now).total_seconds()
        if until>0: sleep(until)
        try:
            if current_day()==now.date().isoformat():
                with engine.begin() as db:
                    write_lock(db)
                    capture_current_report(db,now.date().isoformat())
        except Exception as exc:
            print('midnight snapshot capture failed:',str(exc)[:140],flush=True)
        sleep(1.3)
        try:
            with engine.begin() as db:
                write_lock(db)
                settle_past_days(db)
        except Exception as exc:
            print('midnight settlement failed:',str(exc)[:140],flush=True)

@app.on_event('startup')
def startup():
    db_init()
    if os.environ.get('ENABLE_MIDNIGHT_WORKER','1')=='1':
        threading.Thread(target=midnight_capture_worker,daemon=True,name='member-daily-close').start()


@app.middleware('http')
async def headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response


def hash_pw(password: str) -> str:
    salt = secrets.token_bytes(20)
    iterations = 510000
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
    return f'{iterations}${salt.hex()}${digest.hex()}'


def verify_pw(value, encoded):
    try:
        iteration, salt, digest = encoded.split('$')
        if int(iteration) < 200000: return False
        actual = hashlib.pbkdf2_hmac('sha256', value.encode(), bytes.fromhex(salt), int(iteration))
        return hmac.compare_digest(actual, bytes.fromhex(digest))
    except Exception:
        return False


def session(req):
    if not SESSION_SECRET or not req.cookies.get(COOKIE):
        return None
    try:
        result = serializer.loads(req.cookies[COOKIE], max_age=SESSION_AGE)
        if result.get('role') not in ('admin','viewer'): return None
        # Accounts may be disabled by editing ADMIN_USERS_JSON; reject their existing sessions.
        if result.get('role') == 'admin' and ADMIN_USERS and result.get('username') not in ADMIN_USERS:
            return None
        # Revoke previously issued admin04 cookies when its password changes.
        if result.get('role') == 'admin' and result.get('username') == 'admin04' and ADMIN04_PASSWORD_HASH:
            version = hashlib.sha256(ADMIN04_PASSWORD_HASH.encode()).hexdigest()[:20]
            if not hmac.compare_digest(str(result.get('credential_version','')), version):
                return None
        return result
    except (SignatureExpired, BadSignature):
        return None


def require(req, role='viewer', mutation=False):
    s = session(req)
    if not s or (role == 'admin' and s['role'] != 'admin'):
        raise HTTPException(401 if not s else 403, '请先登录相应权限账号')
    if mutation and not hmac.compare_digest(str(req.headers.get('x-csrf-token', '')), str(s.get('csrf', ''))):
        raise HTTPException(403, '安全校验失败，请刷新后重试')
    return s


class LoginIn(BaseModel):
    role: str
    username: str = Field(default='', max_length=32)
    password: str = Field(min_length=1, max_length=300)


@app.get('/')
def home():
    return FileResponse(ROOT / 'static' / 'index.html')


@app.get('/static/{filename}')
def static(filename: str):
    if filename not in ('app.js', 'style.css'):
        raise HTTPException(404)
    return FileResponse(ROOT / 'static' / filename)


@app.get('/api/health')
def health():
    with engine.connect() as db:
        db.execute(text('SELECT 1'))
    return {'status': 'ok'}


@app.get('/api/me')
def me(req: Request):
    s = session(req)
    return {'role': s['role'] if s else None, 'csrf': s['csrf'] if s else None, 'username': s.get('username','') if s else ''}


@app.post('/api/login')
def login(data: LoginIn, req: Request):
    if not SESSION_SECRET or not (ADMIN_USERS or ADMIN_HASH) or not VIEWER_HASH:
        raise HTTPException(503, '管理员未配置登录凭据')
    if data.role not in ('admin', 'viewer'):
        raise HTTPException(400, '登录角色错误')
    address = req.client.host if req.client else 'unknown'
    now = monotonic()
    with RATE_LOCK:
        failures = [t for t in RATE.get(address, []) if now - t < 900]
        if len(failures) >= 12:
            raise HTTPException(429, '登录尝试次数过多，请稍后再试')
        RATE[address] = failures + [now]
    username = data.username.strip().lower() if data.role == 'admin' else ''
    if data.role == 'admin' and ADMIN_USERS:
        # Also do a real password hash for unknown user to avoid revealing account existence by timing.
        encoded = (ADMIN04_PASSWORD_HASH if username == 'admin04' and ADMIN04_PASSWORD_HASH else None) or ADMIN_USERS.get(username) or next(iter(ADMIN_USERS.values()))
        valid = username in ADMIN_USERS and verify_pw(data.password, encoded)
    else:
        valid = verify_pw(data.password, ADMIN_HASH if data.role == 'admin' else VIEWER_HASH)
        username = username or 'legacy-admin' if data.role == 'admin' else ''
    if not valid:
        raise HTTPException(401, '账号或密码错误')
    with RATE_LOCK:
        RATE.pop(address, None)
    if data.role == 'admin':
        with engine.begin() as db:
            audit(db, 'login', {'role':'admin'}, username)
    csrf = secrets.token_urlsafe(28)
    cookie_data = {'role': data.role, 'username': username, 'csrf': csrf}
    if data.role == 'admin' and username == 'admin04' and ADMIN04_PASSWORD_HASH:
        cookie_data['credential_version'] = hashlib.sha256(ADMIN04_PASSWORD_HASH.encode()).hexdigest()[:20]
    signed = serializer.dumps(cookie_data)
    resp = JSONResponse({'role': data.role, 'username': username, 'csrf': csrf})
    resp.set_cookie(COOKIE, signed, max_age=SESSION_AGE, httponly=True,
                    secure=(os.environ.get('SECURE_COOKIE', '1') == '1'), samesite='strict')
    return resp


@app.post('/api/logout')
def logout(req: Request):
    s=require(req, mutation=True)
    if s.get('role')=='admin':
        with engine.begin() as db:
            audit(db, 'logout', {'role':'admin'}, s.get('username',''))
    resp = JSONResponse({'ok': True})
    resp.delete_cookie(COOKIE)
    return resp


def active_rows(db):
    return [dict(r) for r in db.execute(text('''SELECT id,account,joined_on,parent_id,
       balance_cents,total_withdraw_cents,daily_withdraw_cents,stake_cents,daily_withdraw_on,remark,revision,updated_at
       FROM members WHERE deleted=0 ORDER BY created_at,id''')).mappings().all()]


def sums(rows):
    by_id = {r['id']: r for r in rows}
    kids = {r['id']: [] for r in rows}
    names = ('stake_cents', 'balance_cents', 'total_withdraw_cents', 'daily_withdraw_cents')
    for r in rows:
        # The displayed daily withdrawal is for the current Beijing-calendar day only.
        if r.get('daily_withdraw_on') != current_day():
            r['daily_withdraw_cents'] = 0
    for row in rows:
        if row['parent_id'] in by_id:
            kids[row['parent_id']].append(row['id'])
    memory = {}
    visiting = set()
    def calc(mid):
        if mid in memory: return memory[mid]
        if mid in visiting: raise HTTPException(400, '层级关系出现循环')
        visiting.add(mid)
        r = by_id[mid]
        v = {n: int(r[n]) for n in names}
        cnt = 0
        for cid in kids[mid]:
            child_v, child_cnt = calc(cid)
            for n in names: v[n] += child_v[n]
            cnt += 1 + child_cnt
        visiting.remove(mid)
        memory[mid] = (v, cnt)
        return memory[mid]
    for mid in by_id: calc(mid)
    for mid, (v, cnt) in memory.items():
        r = by_id[mid]
        direct = {n: sum(int(by_id[c][n]) for c in kids[mid]) for n in names}
        for n in names:
            r['subtree_'+n] = v[n]
            r['direct_'+n] = direct[n]
        r['profit_cents'] = r['stake_cents'] - r['total_withdraw_cents']
        r['direct_profit_cents'] = direct['stake_cents'] - direct['total_withdraw_cents']
        r['subtree_profit_cents'] = v['stake_cents'] - v['total_withdraw_cents']
        r['direct_count'] = len(kids[mid])
        r['descendant_count'] = cnt
    # Expose accurate group/root and group path, including nested members.
    for r in rows:
        path_nodes = []
        cur = r
        visited = set()
        while cur and cur['id'] not in visited:
            path_nodes.append(cur)
            visited.add(cur['id'])
            cur = by_id.get(cur['parent_id'])
        path_nodes.reverse()
        r['group_account'] = path_nodes[0]['account']
        r['group_path'] = ' / '.join(item['account'] for item in path_nodes)
        r['level'] = len(path_nodes)
        r['parent_account'] = by_id[r['parent_id']]['account'] if r['parent_id'] in by_id else ''
    totals = {n: sum(int(r[n]) for r in rows) for n in names}
    totals['profit_cents'] = totals['stake_cents'] - totals['total_withdraw_cents']
    return rows, totals


def record_daily_fission(db,rows,day):
    # Percent stored in hundredths of a percent: 1.5% => 150.
    cnt={r['id']:1 for r in rows}
    added={r['id']:int(r['joined_on']==day) for r in rows}
    for r in sorted(rows,key=lambda x:-int(x['level'])):
        p=r['parent_id']
        if p in cnt:
            cnt[p]+=cnt[r['id']];added[p]+=added[r['id']]
    ratio={mid:added[mid]*10000//cnt[mid] if cnt[mid] else 0 for mid in cnt}
    historic={}
    before=(date.fromisoformat(day)-timedelta(days=45)).isoformat()
    for item in db.execute(text('SELECT member_id,business_day,ratio_bp FROM daily_member_fission WHERE business_day>=:start AND business_day<:d'),{'start':before,'d':day}).mappings():
        historic[(item['member_id'],item['business_day'])]=int(item['ratio_bp'])
    existing=db.execute(text('SELECT captured_at FROM daily_member_fission WHERE business_day=:d LIMIT 1'),{'d':day}).scalar()
    now=datetime.now(timezone.utc)
    update=True
    if existing:
        try:update=(now-datetime.fromisoformat(existing)).total_seconds()>=300
        except ValueError:update=True
    if update:
        for mid,bp in ratio.items():
            db.execute(text('''INSERT INTO daily_member_fission (member_id,business_day,ratio_bp,captured_at) VALUES (:i,:d,:r,:t)
                  ON CONFLICT(member_id,business_day) DO UPDATE SET ratio_bp=excluded.ratio_bp,captured_at=excluded.captured_at'''),
                  {'i':mid,'d':day,'r':bp,'t':now.isoformat()})
    for r in rows:
        r['today_fission_pct']=round(ratio[r['id']]/100,2)
        streak=0
        if ratio[r['id']]<150:
            streak=1
            prev=date.fromisoformat(day)-timedelta(days=1)
            for _ in range(45):
                v=historic.get((r['id'],prev.isoformat()))
                if v is None or v>=150:break
                streak+=1;prev-=timedelta(days=1)
        r['low_fission_streak']=streak



# V33 position display is not an instruction or authorization to move money.
def v33_position_limits(stake_cents,direct_count):
    stake=int(stake_cents or 0)
    direct=int(direct_count or 0)
    if stake==500000:
        # 5000 stake: warning above 7500; the suggested amount still targets 7000.
        return 750000,700000,750000
    if stake<=1000000:
        # 10000 stake (and <5000 as previously requested): warn at 15000;
        # suggest a reduction to 13000, and remain open until <=13000.
        return 1500000,1300000,1300000
    # Other larger stake sizes continue their pre-V33 behavior.
    limit=2000000 if direct>=5 else 1300000
    return limit,limit,limit

def v33_sync_position_alerts(db,rows,day):
    counts={}
    for r in rows:
        parent=r.get('parent_id')
        if parent:counts[parent]=counts.get(parent,0)+1
    previous={x['account']:dict(x) for x in
         db.execute(text("SELECT account,opened_on,closed_on,active,updated_at FROM position_alert_state")).mappings()}
    results={}
    for r in rows:
        account=str(r['account']).casefold()
        balance=int(r.get('balance_cents') or 0)
        warn,target,clear=v33_position_limits(r.get('stake_cents',0),counts.get(r['id'],0))
        old=previous.get(account)
        # A warning remains active while a 10000 stake moves from >15000 down
        # toward 13000; it does not disappear at the warning trigger.
        if old and int(old['active'])==1:
            if balance<=clear:
                db.execute(text("""UPDATE position_alert_state
                    SET active=0,closed_on=:day,updated_at=:stamp WHERE account=:account"""),
                    {'day':day,'stamp':utc_now(),'account':account})
                continue
            opened=old['opened_on']
        elif balance>warn:
            opened=day
            db.execute(text("""INSERT INTO position_alert_state
              (account,opened_on,closed_on,active,updated_at)
              VALUES (:account,:opened,NULL,1,:stamp)
              ON CONFLICT(account) DO UPDATE SET
              opened_on=excluded.opened_on,closed_on=NULL,
              active=1,updated_at=excluded.updated_at"""),
              {'account':account,'opened':opened,'stamp':utc_now()})
        else:
            continue
        # Account-based identity keeps the age stable if a backup changes member IDs.
        elapsed=max(0,(date.fromisoformat(day)-date.fromisoformat(opened)).days)
        results[r['id']]={
          'started_on':opened,'elapsed_days':elapsed,'overdue_days':max(0,elapsed-3),
          'remaining_days':max(0,3-elapsed),'warn_cents':warn,
          'target_cents':target,'clear_cents':clear,
          'suggest_cents':max(0,balance-target)
        }
    return results

def v33_capture_team_names(db):
    return [dict(r) for r in db.execute(text("""
        SELECT m.account AS account,t.name AS name,t.updated_at AS updated_at
        FROM team_names t JOIN members m ON m.id=t.member_id
        WHERE m.deleted=0 AND t.name<>''""")).mappings().all()]

def v33_restore_team_names(db,retained):
    # Missing labels after a full restore are restored by account, never by an
    # old UUID. Labels explicitly present in the backup are authoritative.
    rows=db.execute(text("SELECT id,account FROM members WHERE deleted=0")).mappings().all()
    account_to_id={str(r['account']).casefold():r['id'] for r in rows}
    for r in retained:
        mid=account_to_id.get(str(r['account']).casefold())
        if not mid: continue
        db.execute(text("""INSERT INTO team_names(member_id,name,updated_at)
          VALUES (:id,:name,:updated)
          ON CONFLICT(member_id) DO NOTHING"""),
          {'id':mid,'name':r['name'],'updated':r['updated_at']})

@app.get('/api/tree')
def tree(req: Request):
    require(req)
    day=current_day()
    week,month=report_window(day)
    with engine.begin() as db:
        settle_past_days(db,day)
        capture_current_report(db,day)
        rows=active_rows(db)
        position_alerts=v33_sync_position_alerts(db,rows,day)
        events=db.execute(text('''SELECT member_id,business_day,amount_cents
                    FROM daily_withdraw_ledger WHERE business_day>=:start AND business_day<=:day'''),
                    {'start':min(week,month),'day':day}).mappings().all()
        recorded=[r[0] for r in db.execute(text('''SELECT business_day FROM daily_import_days
                    WHERE business_day>=:start AND business_day<=:day'''),
                    {'start':min(week,month),'day':day}).all()]
        since=db.execute(text("SELECT value FROM reporting_meta WHERE name='tracking_since'")).scalar() or day
        names={x['member_id']:x['name'] for x in db.execute(text('SELECT member_id,name FROM team_names')).mappings()}
    output,totals=sums(rows)
    for r in output:r['team_name']=names.get(r['id'],'')
    with engine.begin() as capture_db:record_daily_fission(capture_db,output,day)
    by_id={r['id']:r for r in output}
    for r in output:
        r['week_withdraw_cents']=r['month_withdraw_cents']=0
    for event in events:
        r=by_id.get(event['member_id'])
        if not r:continue
        if event['business_day']>=week:r['week_withdraw_cents']+=int(event['amount_cents'])
        if event['business_day']>=month:r['month_withdraw_cents']+=int(event['amount_cents'])
    return {'members':output,'totals':totals,'position_alerts':position_alerts,
            'updated_at':max((r['updated_at'] for r in rows),default=''),
            'business_day':day,
            'history_coverage':{'tracking_since':since,'imported_days':recorded,
                                'week_start':week,'month_start':month}}


def cents(value):
    try:
        raw = str(value).replace('￥', '').replace('¥', '').strip()
        if not re.fullmatch(r'\d{1,12}(?:\.\d{1,2})?', raw):
            raise ValueError('金额最多12位整数和2位小数')
        return int((Decimal(raw) * 100).to_integral_exact())
    except (InvalidOperation, ValueError):
        raise HTTPException(400, '金额格式不正确，应是非负金额且最多2位小数')


def valid_date(v):
    try:
        date.fromisoformat(v)
    except (ValueError, TypeError):
        raise HTTPException(400, '日期应为YYYY-MM-DD')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
        raise HTTPException(400, '日期应为YYYY-MM-DD')
    return v


class MemberIn(BaseModel):
    account: str = Field(min_length=1, max_length=64)
    joined_on: str
    parent_id: str | None = None
    total_withdraw: str = '0'
    stake: str = '10000'
    parent_account: str | None = None
    remark: str = Field(default='', max_length=20)
    expected_revision: int | None = Field(default=None, ge=1)


def validate_member(data: MemberIn):
    account = data.account.strip()
    if not account or not re.fullmatch(r'[a-zA-Z0-9_.-]+', account):
        raise HTTPException(400, '会员账号只能包含字母、数字、下划线、点和横线')
    valid_date(data.joined_on)
    # Limit by Unicode characters, including punctuation; reject hidden line breaks.
    if any(ord(c) < 32 for c in data.remark):
        raise HTTPException(400, '备注不能包含换行或控制字符')
    money = cents(data.total_withdraw)
    stake = cents(data.stake)
    if stake <= 0 or stake > 10**16:
        raise HTTPException(400, '建仓资金必须是有效的正数')
    return account, money, stake


def validate_stake_for_level(db, parent, stake):
    """All levels accept any valid positive stake; still validate the ancestor chain."""
    depth=1
    seen=set()
    while parent is not None:
        if parent in seen:raise HTTPException(400,'层级关系出现循环')
        seen.add(parent)
        data=db.execute(text('SELECT parent_id FROM members WHERE id=:i AND deleted=0'),{'i':parent}).mappings().first()
        if not data:raise HTTPException(400,'推荐人不存在')
        depth+=1
        parent=data['parent_id']
        if depth>20000:raise HTTPException(400,'会员层级过深')


def parent_ok(db, parent, editing=None):
    if parent is None: return
    seen = set()
    p = parent
    while p:
        if p == editing or p in seen:
            raise HTTPException(400, '不能把会员放在自己或下级名下')
        seen.add(p)
        r = db.execute(text('SELECT parent_id,deleted FROM members WHERE id=:id'), {'id': p}).mappings().first()
        if not r or r['deleted']:
            raise HTTPException(400, '直属上级不存在')
        p = r['parent_id']


def resolved_parent(db, data: MemberIn):
    # Frontend supplies the exact member account, not a select of opaque ids.
    account = (data.parent_account or '').strip()
    if not account:
        return data.parent_id
    parent = db.execute(text('SELECT id FROM members WHERE account=:a AND deleted=0'), {'a': account}).mappings().first()
    if not parent:
        raise HTTPException(400, '找不到填写的上级会员账号，请重新搜索选择')
    return parent['id']


def write_lock(db):
    # Serializes administrative writes and import commits for the same Render database.
    if engine.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(20261104)'))


def audit(db, event, detail, username=''):
    if username:
        detail = {**detail, 'operator': username}
    db.execute(text('INSERT INTO audit_logs(id,event,detail,created_at) VALUES (:id,:e,:d,:t)'),
               {'id': str(uuid.uuid4()), 'e': event, 'd': json.dumps(detail, ensure_ascii=False), 't': datetime.now(timezone.utc).isoformat(timespec='microseconds')})


# Snapshot every field that affects a record or its optimistic revision. A changed
# revision blocks unsafe undo even when the values happen to match.
SNAPSHOT_FIELDS = ('id','account','joined_on','parent_id','balance_cents',
                   'total_withdraw_cents','daily_withdraw_cents','stake_cents',
                   'daily_withdraw_on','remark','revision','deleted','created_at','updated_at')


def snapshot(db, mid):
    row = db.execute(text('SELECT * FROM members WHERE id=:id'), {'id': mid}).mappings().first()
    return {k: row[k] for k in SNAPSHOT_FIELDS} if row else None


def record_undo(db, operator, event, label, changes):
    if not operator: raise HTTPException(403, '管理员账号缺失')
    # Preserve strict event chronology even when two actions share the same system clock tick.
    when=datetime.now(timezone.utc)
    last=db.execute(text('SELECT MAX(created_at) FROM undo_actions')).scalar()
    if last:
        last_time=datetime.fromisoformat(last)
        if last_time.tzinfo is None: last_time=last_time.replace(tzinfo=timezone.utc)
        if when<=last_time: when=last_time+timedelta(microseconds=1)
    db.execute(text('''INSERT INTO undo_actions(id,operator,event,label,changes_json,created_at)
                       VALUES (:id,:operator,:event,:label,:changes,:created)'''),
               {'id':str(uuid.uuid4()),'operator':operator,'event':event,'label':label[:180],
                'changes':json.dumps(changes,ensure_ascii=False),
                'created':when.isoformat(timespec='microseconds')})


def latest_undo(db):
    return db.execute(text('''SELECT * FROM undo_actions WHERE undone=0
                              ORDER BY created_at DESC, id DESC LIMIT 1''')).mappings().first()


@app.get('/api/admin/undo/status')
def undo_status(req: Request):
    actor = require(req,'admin').get('username','')
    with engine.connect() as db:
        last = latest_undo(db)
    if not last:
        return {'can_undo':False,'reason':'暂时没有可撤回的修改'}
    if last['operator'] != actor:
        return {'can_undo':False,'reason':f"最近一次修改由 {last['operator']} 完成，不能撤回其他管理员的操作",
                'last_operator':last['operator']}
    return {'can_undo':True,'action_id':last['id'],'event':last['event'],
            'label':last['label'],'created_at':last['created_at']}


@app.post('/api/admin/undo')
def undo_last(data: dict, req: Request):
    operator = require(req,'admin',True).get('username','')
    expected = str(data.get('action_id',''))
    with engine.begin() as db:
        write_lock(db)
        settle_past_days(db)
        last = latest_undo(db)
        if not last: raise HTTPException(409,'没有可以撤回的操作')
        if last['operator'] != operator:
            raise HTTPException(409,'其他管理员已修改数据，不可撤回别人的操作，请先核对操作日志')
        if expected != last['id']:
            raise HTTPException(409,'撤回前数据又发生了变化，请重新检查最新操作')
        changes = json.loads(last['changes_json'])
        # First validate *all* rows before changing *any* row. Never partially undo.
        for change in changes:
            now = snapshot(db,change['id'])
            if now != change['after']:
                raise HTTPException(409, f"会员 {change['account']} 数据已改变，停止撤回以免覆盖其他人的修改")
            if change['before'] is None:
                descendants = db.execute(text('SELECT COUNT(*) FROM members WHERE parent_id=:id AND deleted=0'),
                                         {'id':change['id']}).scalar()
                if descendants:
                    raise HTTPException(409,'新会员已有下级，不能撤回其创建操作')
        changed_at=utc_now()
        for change in changes:
            old=change['before']
            if old is None:
                # Soft-delete an undone creation so audit and foreign keys stay intact.
                db.execute(text('''UPDATE members SET deleted=1,revision=revision+1,updated_at=:t
                                   WHERE id=:id'''),{'id':change['id'],'t':changed_at})
            else:
                updates={key:old[key] for key in SNAPSHOT_FIELDS
                         if key not in ('id','revision','updated_at','created_at')}
                updates['revision']=int(change['after']['revision'])+1
                updates['updated_at']=changed_at
                updates['id']=change['id']
                clauses=','.join(f'{k}=:{k}' for k in updates if k!='id')
                db.execute(text(f'UPDATE members SET {clauses} WHERE id=:id'),updates)
        if last['event']=='import':
            # Restore ledger alongside the imported member snapshots in this transaction.
            for change in changes:
                before,after=change['before'],change['after']
                affected=after.get('daily_withdraw_on') if after else None
                if not affected: continue
                prior=(before.get('daily_withdraw_cents',0) if before and
                       before.get('daily_withdraw_on')==affected else 0)
                set_daily_ledger(db,change['id'],affected,prior)
        db.execute(text('UPDATE undo_actions SET undone=1,undone_at=:now WHERE id=:id'),
                   {'id':last['id'],'now':changed_at})
        audit(db,'undo',{'action_id':last['id'],'undone_event':last['event'],
                         'label':last['label'],'affected':len(changes)},operator)
        capture_current_report(db)
    return {'ok':True,'undone':last['label'],'affected':len(changes)}


@app.get('/api/admin/logs')
def admin_logs(req: Request, limit: int = 100):
    require(req,'admin')
    limit=max(1,min(200,limit))
    with engine.connect() as db:
        entries=db.execute(text('''SELECT event,detail,created_at FROM audit_logs
                                   ORDER BY created_at DESC,id DESC LIMIT :max'''),
                           {'max':limit}).mappings().all()
    return {'logs':[{'event':r['event'],'created_at':r['created_at'],
                     'operator':(json.loads(r['detail']).get('operator') or '系统'),
                     'detail':json.loads(r['detail'])} for r in entries]}


@app.post('/api/members')
def create_member(data: MemberIn, req: Request):
    operator = require(req, 'admin', True)
    account, withdrawn, stake = validate_member(data)
    mid = str(uuid.uuid4())
    with engine.begin() as db:
        write_lock(db)
        settle_past_days(db)
        parent = resolved_parent(db, data)
        parent_ok(db, parent)
        validate_stake_for_level(db,parent,stake)
        try:
            db.execute(text('''INSERT INTO members(id,account,joined_on,parent_id,total_withdraw_cents,stake_cents,remark,created_at,updated_at)
                 VALUES (:id,:a,:j,:p,:w,:stake,:remark,:t,:t)'''),
                 {'id': mid, 'a': account, 'j': data.joined_on, 'p': parent, 'w': withdrawn, 'stake': stake, 'remark':data.remark.strip(), 't': utc_now()})
            record_undo(db,operator.get('username',''),'create',f'新增会员 {account}',
                        [{'id':mid,'account':account,'before':None,'after':snapshot(db,mid)}])
            audit(db, 'create', {'account': account,'remark':data.remark.strip()},operator.get('username',''))
            capture_current_report(db)
        except IntegrityError:
            raise HTTPException(409, '会员账号已存在')
    return {'ok': True, 'id': mid}


@app.put('/api/members/{mid}')
def update_member(mid: str, data: MemberIn, req: Request):
    operator = require(req, 'admin', True)
    account, withdrawn, stake = validate_member(data)
    if data.expected_revision is None:
        raise HTTPException(409, '编辑信息已过期，请刷新会员资料后再修改')
    with engine.begin() as db:
        write_lock(db)
        settle_past_days(db)
        old = db.execute(text('SELECT * FROM members WHERE id=:id AND deleted=0'), {'id': mid}).mappings().first()
        if not old: raise HTTPException(404, '会员不存在')
        if old['revision'] != data.expected_revision:
            raise HTTPException(409, '该会员资料已被另一名管理员更新，请刷新后再操作')
        parent = resolved_parent(db, data)
        parent_ok(db, parent, mid)
        validate_stake_for_level(db,parent,stake)
        try:
            updated = db.execute(text("""UPDATE members SET account=:a,joined_on=:j,parent_id=:p,
                total_withdraw_cents=:w,stake_cents=:stake,remark=:remark,updated_at=:t,revision=revision+1
                WHERE id=:id AND revision=:expected"""),
                {'a': account, 'j': data.joined_on, 'p': parent, 'w': withdrawn, 'stake':stake,
                 'remark':data.remark.strip(), 't': utc_now(), 'id': mid,'expected':data.expected_revision})
            if updated.rowcount != 1:
                raise HTTPException(409, '该会员资料已被其他管理员修改，请刷新后重试')
            record_undo(db,operator.get('username',''),'update',f'编辑会员 {account}',
                        [{'id':mid,'account':account,'before':{k:old[k] for k in SNAPSHOT_FIELDS},'after':snapshot(db,mid)}])
            audit(db, 'update', {'before': {'account': old['account'],'parent': old['parent_id'],
                'total': old['total_withdraw_cents'], 'stake':old['stake_cents'],'remark':old['remark']},
                'after': {'account': account,'parent': parent, 'total': withdrawn,
                'stake':stake,'remark':data.remark.strip()}},operator.get('username',''))
            capture_current_report(db)
        except IntegrityError:
            raise HTTPException(409, '会员账号已存在')
    return {'ok': True}


@app.delete('/api/members/{mid}')
def delete_member(mid: str, req: Request, expected_revision: int | None = None):
    operator = require(req, 'admin', True)
    if expected_revision is None:
        raise HTTPException(409, '缺少记录版本，请刷新后再操作')
    with engine.begin() as db:
        write_lock(db)
        settle_past_days(db)
        row = db.execute(text('SELECT account,revision FROM members WHERE id=:id AND deleted=0'), {'id': mid}).mappings().first()
        if not row: raise HTTPException(404, '会员不存在')
        if row['revision'] != expected_revision:
            raise HTTPException(409, '该会员已被其他管理员更新，请先刷新再决定是否删除')
        child = db.execute(text('SELECT COUNT(*) FROM members WHERE parent_id=:id AND deleted=0'), {'id':mid}).scalar()
        if child: raise HTTPException(409, '会员还有下级，请先调整归属')
        before=snapshot(db,mid)
        db.execute(text('UPDATE members SET deleted=1,updated_at=:t,revision=revision+1 WHERE id=:id'), {'id':mid, 't':utc_now()})
        record_undo(db,operator.get('username',''),'delete',f'删除会员 {row["account"]}',
                    [{'id':mid,'account':row['account'],'before':before,'after':snapshot(db,mid)}])
        audit(db, 'delete', {'account': row['account']}, operator.get('username',''))
        capture_current_report(db)
    return {'ok': True}


def roster_stamp(rows):
    source = json.dumps(sorted([f"{r['id']}:{r['account']}:{r['revision']}:{r['updated_at']}:{r['balance_cents']}:{r['total_withdraw_cents']}:{r['daily_withdraw_cents']}:{r.get('daily_withdraw_on')}" for r in rows]), ensure_ascii=False)
    return hashlib.sha256(source.encode()).hexdigest()


def parse_lines(lines, mode):
    """Accept pasted whitespace/CSV/TSV or Excel rows. In three-column mode,
    a blank/missing third column is zero, NOT a fatal format error.
    Explicit empty columns remain in place (e.g. 'account\t\t100').
    """
    expected = 3 if mode == 'both' else 2
    rows, errors, duplicates, padded_daily = {}, [], [], []
    for i, line in enumerate(lines, 1):
        if isinstance(line, str):
            line = line.replace('\ufeff', '').strip()
            if not line: continue
            if '\t' in line:
                parts = [part.strip() for part in line.split('\t')]
            elif any(s in line for s in (',', '，', ';', '；', '|')):
                parts = [part.strip() for part in re.split(r'[,，;；|]', line)]
            else:
                parts = line.split()
        else:
            parts = [str(x).strip() if x is not None else '' for x in line[:max(expected, len(line))]]
            if not any(parts): continue
        # Extra empty trailing columns are harmless (common with Excel exports).
        while len(parts) > expected and not parts[-1]:
            parts.pop()
        if not parts or not any(parts): continue
        if parts[0].lower() in ('会员账号', '账号', 'account', '账户', '会员帐号'):
            continue
        if mode == 'both' and len(parts) == 2:
            parts.append('0')
            padded_daily.append(i)
        elif mode == 'both' and len(parts) == 3 and parts[2] == '':
            parts[2] = '0'
            padded_daily.append(i)
        if len(parts) != expected:
            errors.append(f'第{i}行格式错误：需要账号+金额' + ('+当日提现（第三列可留空）' if mode=='both' else ''))
            continue
        account = parts[0]
        if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,64}', account):
            errors.append(f'第{i}行会员账号格式错误')
            continue
        # Explicit empty columns are treated as zero only in three-column import.
        if mode == 'both' and parts[1] == '':
            parts[1] = '0'
        try:
            values = [cents(v) for v in parts[1:]]
        except HTTPException:
            errors.append(f'第{i}行 {account} 金额格式错误（不能有负数或超过两位小数）')
            continue
        if account in rows:
            duplicates.append(account)
        rows[account] = values
    return rows, errors, duplicates, padded_daily


def excel_account(cell):
    """Preserve leading zeros for numeric Excel cells formatted as 000000."""
    value = cell.value
    if value is None: return ''
    if isinstance(value, str): return value.strip()
    if isinstance(value, int) or isinstance(value, float) and value.is_integer():
        fmt = str(cell.number_format or '')
        if re.fullmatch(r'0{2,64}', fmt):
            return str(int(value)).zfill(len(fmt))
    return str(value).strip()


@app.post('/api/import/preview')
async def import_preview(req: Request, mode: str = Form(...), content: str = Form(''), upload: UploadFile | None = File(None)):
    require(req, 'admin', True)
    if mode not in ('balance', 'daily', 'both'):
        raise HTTPException(400, '只能导入余额、当日提现或两项同时')
    if upload and upload.filename:
        raw = await upload.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            raise HTTPException(400, '文件不能超过5MB')
        if upload.filename.lower().endswith(('.xlsx','.xlsm')):
            try:
                workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
                lines = []
                width = 3 if mode == 'both' else 2
                for row in workbook.active.iter_rows():
                    vals = [excel_account(row[0])] if row else ['']
                    vals += [str(cell.value).strip() if cell.value is not None else '' for cell in row[1:width]]
                    lines.append(vals)
                workbook.close()
            except Exception:
                raise HTTPException(400, 'Excel解析失败，请确认文件有效')
        else:
            try: decoded = raw.decode('utf-8-sig')
            except UnicodeDecodeError: decoded = raw.decode('gb18030')
            lines = decoded.splitlines()
    else:
        lines = content.splitlines()
    if len(lines) > 10000: raise HTTPException(400, '最多支持10000行')
    parsed, errors, duplicate, padded_daily = parse_lines(lines, mode)
    if not parsed: raise HTTPException(400, '未找到有效会员账号和金额；请检查输入格式')
    with engine.begin() as db:
        settle_past_days(db)
        current = active_rows(db)
        known = {r['account'] for r in current}
        matches = sorted(known & set(parsed))
        unknown = sorted(set(parsed) - known)
        if not matches:
            errors.append('没有匹配到任何已录入的会员账号：请先添加会员，或检查账号大小写、空格及前导0')
        jobid = str(uuid.uuid4())
        stamp = roster_stamp(current)
        if not errors and not duplicate and matches:
            db.execute(text('''INSERT INTO import_jobs(id,mode,rows_json,roster_stamp,created_at)
                VALUES (:id,:mode,:rows,:stamp,:created)'''),
                {'id': jobid, 'mode': mode, 'rows': json.dumps(parsed), 'stamp': stamp, 'created': utc_now()})
        else:
            jobid = None
    today = current_day()
    delta = 0
    if mode in ('daily', 'both'):
        pos = 1 if mode == 'both' else 0
        for r in current:
            old_daily = int(r['daily_withdraw_cents']) if r.get('daily_withdraw_on') == today else 0
            new_daily = int(parsed.get(r['account'], [0]*(pos+1))[pos])
            delta += new_daily-old_daily
    if errors and jobid:
        with engine.begin() as db:
            db.execute(text('DELETE FROM import_jobs WHERE id=:id'), {'id':jobid})
        jobid = None
    return {'job_id': jobid, 'mode': mode, 'matched': len(matches), 'missing': len(current)-len(matches),
            'daily_date': today, 'withdraw_delta_cents': delta,
            'unmatched': unknown[:50], 'unmatched_count': len(unknown), 'duplicates': duplicate[:50],
            'errors': errors[:50], 'valid': jobid is not None, 'filled_daily_zero_rows': padded_daily[:50], 'filled_daily_zero_count': len(padded_daily),
            'summary': ('余额及当日提现只保留最新上传结果；累计总提现不在同日反复累计，待跨日结算时只计入最终快照。' if mode!='balance' else '只更新余额，不影响提现数据。') + ' 未出现账号的所选字段置零；上传中未匹配的账号不会自动创建会员。'}


@app.post('/api/import/{jobid}/confirm')
def import_confirm(jobid: str, req: Request):
    operator = require(req, 'admin', True)
    with engine.begin() as db:
        write_lock(db)
        settle_past_days(db)
        job = db.execute(text('SELECT * FROM import_jobs WHERE id=:id'), {'id':jobid}).mappings().first()
        if not job or job['applied']:
            raise HTTPException(404, '导入预览已失效或已提交')
        created = datetime.fromisoformat(job['created_at'])
        if datetime.now(timezone.utc) - created > timedelta(minutes=30):
            raise HTTPException(409, '预览超过30分钟，请重新上传')
        if job['mode'] in ('daily', 'both') and created.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat() != current_day():
            raise HTTPException(409, '本次提现预览已跨过北京时间零点，请重新上传当日数据')
        rows = active_rows(db)
        if job['roster_stamp'] != roster_stamp(rows):
            raise HTTPException(409, '会员名单发生变化，请重新预览后导入')
        data = json.loads(job['rows_json'])
        rows = active_rows(db)
        if job['roster_stamp'] != roster_stamp(rows):
            raise HTTPException(409, '财务数据或会员名单已更新，请重新预览导入')
        use_balance = job['mode'] in ('balance', 'both')
        use_daily = job['mode'] in ('daily', 'both')
        today = current_day()
        idx_daily = 1 if job['mode']=='both' else 0
        withdraw_delta = 0
        count = 0
        before_import={r['id']:snapshot(db,r['id']) for r in rows}
        for r in rows:
            values = data.get(r['account'])
            if values is not None: count += 1
            params = {'id':r['id'], 't':utc_now()}
            updates = ['updated_at=:t','revision=revision+1']
            if use_balance:
                params['balance'] = values[0] if values is not None else 0
                updates.append('balance_cents=:balance')
            if use_daily:
                prior_daily = int(r['daily_withdraw_cents']) if r.get('daily_withdraw_on') == today else 0
                new_daily = values[idx_daily] if values is not None else 0
                delta = new_daily - prior_daily
                withdraw_delta += delta
                params.update({'today':today,'daily':new_daily})
                # Today's withdrawals are provisional; settle once after midnight.
                updates.extend(['daily_withdraw_cents=:daily','daily_withdraw_on=:today'])
            db.execute(text(f"UPDATE members SET {','.join(updates)} WHERE id=:id"), params)
            if use_daily:
                set_daily_ledger(db,r['id'],today,new_daily)
        if use_daily:
            exists=db.execute(text('SELECT business_day FROM daily_import_days WHERE business_day=:d'),
                              {'d':today}).first()
            if not exists:
                db.execute(text('INSERT INTO daily_import_days(business_day,recorded_at) VALUES (:d,:t)'),
                           {'d':today,'t':utc_now()})
        # Refresh the report in the SAME transaction as the import.
        capture_current_report(db,today)
        db.execute(text('UPDATE import_jobs SET applied=1 WHERE id=:id'), {'id':jobid})
        record_undo(db,operator.get('username',''),'import',
                    f'批量更新{count}位会员（{job["mode"]}模式）',
                    [{'id':r['id'],'account':r['account'],'before':before_import[r['id']],
                      'after':snapshot(db,r['id'])} for r in rows])
        audit(db, 'import', {'mode':job['mode'], 'matched':count, 'missing':len(rows)-count,
                             'withdraw_delta_cents':withdraw_delta, 'daily_date':today if use_daily else None},operator.get('username',''))
    return {'ok':True, 'matched':count, 'missing':len(rows)-count, 'withdraw_delta_cents':withdraw_delta}


def filter_export_rows(rows, root_account):
    if not root_account:
        return rows
    candidate = next((r for r in rows if r['account'] == root_account), None)
    if not candidate:
        raise HTTPException(404, '找不到要导出的节点账号')
    current = {candidate['id']}
    selected = set(current)
    for _ in range(len(rows)):
        additions = {r['id'] for r in rows if r['parent_id'] in current and r['id'] not in selected}
        if not additions: break
        selected.update(additions)
        current = additions
    return [r for r in rows if r['id'] in selected]


def export_columns():
    heads = ['会员账号', '加入日期', '所在分组', '直属上级账号', '所属关系路径', '层级', '直属人数', '全部下级人数','备注']
    heads += [f'{group}{n}' for group in ('本人', '直属一层', '节点全层级') for n in ('建仓资金','余额','总提现','当日提现','输赢')]
    return heads


def export_values(r):
    metric_names = ['stake_cents','balance_cents','total_withdraw_cents','daily_withdraw_cents','profit_cents']
    fields = [r['account'], r['joined_on'], r['group_account'], r['parent_account'], r['group_path'], r['level'], r['direct_count'], r['descendant_count'],r.get('remark','')]
    for prefix in ('', 'direct_', 'subtree_'):
        fields.extend([f"{r[prefix+n]/100:.0f}" if n in ("total_withdraw_cents", "daily_withdraw_cents") else f"{r[prefix+n]/100:.2f}" for n in metric_names])
    return fields




def node_layer_summary(rows, account):
    """One personal row followed by exact-generation totals; no repeated members."""
    lookup = {r['account']: r for r in rows}
    root = lookup.get(account)
    if root is None:
        raise HTTPException(404, '找不到要导出的会员账号')
    children = {}
    for r in rows:
        children.setdefault(r['parent_id'], []).append(r)
    fields = ('stake_cents', 'balance_cents', 'total_withdraw_cents', 'daily_withdraw_cents')

    def aggregate(group, depth):
        amounts = {k: sum(int(r[k]) for r in group) for k in fields}
        amounts['profit_cents'] = amounts['stake_cents'] - amounts['total_withdraw_cents']
        return {'depth': depth, 'member_count': len(group), **amounts}

    output = [aggregate([root], 0)]
    seen = {root['id']}
    frontier = [root]
    depth = 0
    while frontier:
        next_members = []
        for r in frontier:
            for child in children.get(r['id'], []):
                if child['id'] in seen:
                    raise HTTPException(400, '会员上下级关系包含重复或循环')
                seen.add(child['id'])
                next_members.append(child)
        if not next_members:
            break
        depth += 1
        output.append(aggregate(next_members, depth))
        frontier = next_members
    return root, output


@app.get('/api/export/layers.xlsx')
def export_node_layers(req: Request, account: str):
    # Viewers may export exactly the statistics they are already allowed to see;
    # never expose any data without a valid member or administrator session.
    require(req)
    with engine.connect() as db:
        rows, _ = sums(active_rows(db))
    root, layer_rows = node_layer_summary(rows, account)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = '逐层统计'
    ws.merge_cells('A1:H1')
    ws['A1'] = f'会员 {root["account"]} · 节点逐层汇总'
    ws['A1'].font = Font(name='Microsoft YaHei', size=16, bold=True, color='FFFFFF')
    ws['A1'].fill = PatternFill('solid', fgColor='1F4071')
    ws['A1'].alignment = Alignment(horizontal='left', vertical='center', indent=1)
    ws.row_dimensions[1].height = 35
    ws.merge_cells('A2:H2')
    ws['A2'] = f'本人加入日期：{root["joined_on"]}  |  下级总人数：{sum(x["member_count"] for x in layer_rows[1:])}  |  按与本人的实际关系层级分别汇总（不重复计数）'
    ws['A2'].font = Font(name='Microsoft YaHei', size=10, color='52647A')
    ws['A2'].alignment = Alignment(vertical='center', indent=1)
    ws.row_dimensions[2].height = 27
    headers = ['数据层级', '会员账号', '该层会员数', '建仓资金', '当前余额', '总提现', '当日提现', '输赢（建仓－总提现）']
    for idx, header in enumerate(headers, 1):
        cell = ws.cell(4, idx, header)
        cell.font = Font(name='Microsoft YaHei', size=10, bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='315D92')
        cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[4].height = 28
    for row_index, item in enumerate(layer_rows, start=5):
        desc = '本人' if item['depth'] == 0 else f'第{item["depth"]}层汇总'
        ws.cell(row_index, 1, desc)
        cell_account = ws.cell(row_index, 2, root['account'] if item['depth'] == 0 else '—')
        cell_account.number_format = '@'
        ws.cell(row_index, 3, item['member_count'])
        amounts = [item['stake_cents'], item['balance_cents'], item['total_withdraw_cents'], item['daily_withdraw_cents'], item['profit_cents']]
        for col, cents_value in enumerate(amounts, 4):
            cell = ws.cell(row_index, col, cents_value / 100)
            cell.number_format = '#,##0;[Red]-#,##0;0' if col in (6, 7) else '#,##0.00;[Red]-#,##0.00;0.00'
            cell.alignment = Alignment(horizontal='right', vertical='center')
            cell.font = Font(name='Microsoft YaHei', size=10, color='C62828' if cents_value < 0 else '111827')
        ws.row_dimensions[row_index].height = 27
        for col in range(1, 9):
            c = ws.cell(row_index, col)
            if col <= 3: c.alignment = Alignment(vertical='center', horizontal='center' if col == 3 else 'left')
            if col <= 3: c.font = Font(name='Microsoft YaHei', size=10, bold=col == 1, color='1F3557')
            c.fill = PatternFill('solid', fgColor='EEF4FB' if item['depth'] == 0 else ('FFFFFF' if row_index % 2 == 0 else 'F7F9FC'))
            c.border = Border(bottom=Side(style='hair', color='E1E9F3'))
    ws.freeze_panes = 'D5'
    ws.auto_filter.ref = f'A4:H{max(5, 4 + len(layer_rows))}'
    for col, width in zip('ABCDEFGH', [21, 21, 16, 20, 20, 20, 20, 26]):
        ws.column_dimensions[col].width = width
    out = io.BytesIO()
    wb.save(out)
    from urllib.parse import quote
    nice_name = quote(f'{root["account"]}_逐层汇总.xlsx')
    return Response(out.getvalue(), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f"attachment; filename=member-layers.xlsx; filename*=UTF-8''{nice_name}"})


@app.get('/api/export.csv')
def export(req: Request, root_account: str | None = None):
    require(req, 'admin')
    with engine.connect() as db:
        rows, _ = sums(active_rows(db))
    rows = filter_export_rows(rows, root_account)
    handle = io.StringIO()
    writer = csv.writer(handle)
    writer.writerow(export_columns())
    for r in rows:
        writer.writerow(export_values(r))
    return Response('\ufeff'+handle.getvalue(),media_type='text/csv;charset=utf-8',
                    headers={'Content-Disposition':'attachment; filename="members-node.csv"' if root_account else 'attachment; filename="members-all.csv"'})



@app.get('/api/export/team.xlsx')
def export_team_styled(req: Request, account: str):
    """Read-only, admin-authenticated team Excel: overview, joined-on sorted detail and level totals."""
    require(req, 'admin')
    from datetime import datetime
    from urllib.parse import quote
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.formatting.rule import FormulaRule

    with engine.connect() as db:
        all_members, _ = sums(active_rows(db))
    root, layer_rows = node_layer_summary(all_members, account)
    team = filter_export_rows(all_members, account)
    team.sort(key=lambda r: (str(r.get('joined_on') or '9999-12-31'), str(r['account']).casefold()))
    if not team:
        raise HTTPException(404, '没有找到团队成员')
    children = {}
    for r in team:
        children.setdefault(r['parent_id'], []).append(r)
    depths = {root['id']: 0}
    pending = [root]
    for parent in pending:
        for child in children.get(parent['id'], []):
            if child['id'] not in depths:
                depths[child['id']] = depths[parent['id']] + 1
                pending.append(child)
    if len(depths) != len(team):
        raise HTTPException(400, '成员关系存在异常，请先核查')

    blue='17375E'; green='087C46'; red='C62828'; dark='23364F'; yellow='C58A00'
    border=Border(bottom=Side(style='hair',color='D6E0ED'),
                  right=Side(style='hair',color='D6E0ED'))
    moneyfmt='#,##0;[Red]-#,##0;0'
    def crosses_position_line(r):
        # Use the formal production V33 alert TRIGGER, not Whale's independent 130% limit.
        trigger,_,_=v33_position_limits(int(r.get('stake_cents') or 0),int(r.get('direct_count') or 0))
        return int(r.get('balance_cents') or 0)>trigger

    wb=Workbook()
    def title(ws,label,n):
        ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=n)
        cell=ws.cell(1,1,label);cell.fill=PatternFill('solid',fgColor=blue)
        cell.font=Font(name='Microsoft YaHei',size=16,color='FFFFFF',bold=True)
        cell.alignment=Alignment(vertical='center',indent=1)
        ws.row_dimensions[1].height=40
        ws.sheet_view.showGridLines=False
    def headers(ws,row,labels):
        for col,label in enumerate(labels,1):
            c=ws.cell(row,col,label)
            c.fill=PatternFill('solid',fgColor='315D92')
            c.font=Font(name='Microsoft YaHei',size=10,bold=True,color='FFFFFF')
            c.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
            c.border=border
        ws.row_dimensions[row].height=30
    def cell(ws,row,col,value,kind='',stripe=False):
        c=ws.cell(row,col,value);c.border=border
        c.fill=PatternFill('solid',fgColor='FFF5BF' if kind=='alert_balance' else ('F3F7FC' if stripe else 'FFFFFF'))
        color=yellow if kind=='alert_balance' else green if kind=='recharge' else red if kind=='withdraw' else (
            green if value>0 else red if value<0 else dark
            ) if kind=='profit' and isinstance(value,(int,float)) else dark
        c.font=Font(name='Microsoft YaHei',size=10,color=color,
                    bold=kind in ('recharge','withdraw','profit','alert_balance'))
        c.alignment=Alignment(horizontal='center',
                              vertical='center',wrap_text=True)
        if isinstance(value,(int,float)) and kind not in ('count','level'):
            c.number_format=moneyfmt
        if kind=='text':
            c.data_type='s'
            c.number_format='@'
        return c

    ws=wb.active;ws.title='团队汇总'
    title(ws,'团队数据汇总 · '+root['account'],8)
    ws.merge_cells('A2:H2')
    ws['A2']='范围：负责人及全部下级  |  导出时间：'+datetime.now().strftime('%Y-%m-%d %H:%M')
    ws['A2'].font=Font(name='Microsoft YaHei',size=10,color='637C9D')
    ws.row_dimensions[2].height=27
    headers(ws,4,['项目','数值','项目','数值','项目','数值'])
    fields=('stake_cents','balance_cents','total_withdraw_cents','daily_withdraw_cents','profit_cents')
    totals={k:sum(int(r.get(k) or 0) for r in team) for k in fields}
    count=len(team)
    summary=[
        [('负责人账号',root['account'],'text'),('团队总人数',count,'count'),('直属人数',len(children.get(root['id'],[])),'count')],
        [('全部下级人数',count-1,'count'),('团队充值/建仓',totals['stake_cents']/100,'recharge'),('团队总提现',totals['total_withdraw_cents']/100,'withdraw')],
        [('团队总余额',totals['balance_cents']/100,''),('团队平均余额',totals['balance_cents']/100/count,''),('团队总输赢',totals['profit_cents']/100,'profit')],
        [('团队今日提现',totals['daily_withdraw_cents']/100,'withdraw'),('负责人加入日期',str(root.get('joined_on') or ''),'text'),('团队层级数',max(depths.values())+1,'count')],
    ]
    for rn,groups in enumerate(summary,5):
        ws.row_dimensions[rn].height=32
        for k,(name,value,kind) in enumerate(groups):
            cell(ws,rn,k*2+1,name,stripe=rn%2==0)
            cell(ws,rn,k*2+2,value,kind,stripe=rn%2==0)
    ws.merge_cells('A10:H10')
    ws['A10']='口径：充值对应系统本人建仓；输赢按系统原公式（建仓－累计提现）；本人及下级每位只汇总一次。'
    ws['A10'].font=Font(name='Microsoft YaHei',size=9,color='637C9D')

    ws.merge_cells('A11:H11')
    ws['A11']='黄色余额：本人当前余额严格超过正式版原压仓告警触发线（按本人建仓及直属人数计算）。'
    ws['A11'].font=Font(name='Microsoft YaHei',size=9,color=yellow,bold=True)
    # Show all members beneath the overview, including the stored remark as name.
    ws.merge_cells('A12:H12')
    ws['A12']='团队成员明细 · 按加入日期从早到晚（负责人及全部下级）'
    ws['A12'].font=Font(name='Microsoft YaHei',size=12,bold=True,color='FFFFFF')
    ws['A12'].fill=PatternFill('solid',fgColor=blue)
    ws['A12'].alignment=Alignment(horizontal='center',vertical='center')
    ws.row_dimensions[12].height=32
    headers(ws,13,['姓名','会员账号','加入日期','充值/建仓','累计提现','当前余额','输赢','直推人数'])
    for idx,member in enumerate(team,14):
        values=[str(member.get('remark') or ''),str(member['account']),
                str(member.get('joined_on') or ''),
                int(member['stake_cents'])/100,int(member['total_withdraw_cents'])/100,
                int(member['balance_cents'])/100,int(member['profit_cents'])/100,
                int(member.get('direct_count') or 0)]
        danger=crosses_position_line(member)
        for col,value in enumerate(values,1):
            kind='text' if col in (1,2,3) else ('recharge' if col==4 else
                'withdraw' if col==5 else 'alert_balance' if col==6 and danger else
                'profit' if col==7 else 'count' if col==8 else '')
            cell(ws,idx,col,value,kind,stripe=idx%2==0)
        ws.row_dimensions[idx].height=26
    ws.auto_filter.ref=f'A13:H{13+count}'
    ws.print_title_rows='1:2'
    ws.conditional_formatting.add(f'F14:F{13+count}',
        FormulaRule(formula=['F14>IF(D14=5000,7500,IF(D14<=10000,15000,IF(H14>=5,20000,13000)))'],
                    font=Font(name='Microsoft YaHei',bold=True,color=yellow),
                    fill=PatternFill('solid',fgColor='FFF5BF')))
    for col,width in zip('ABCDEFGH',[24,23,17,22,22,22,22,15]):
        ws.column_dimensions[col].width=width
    ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_setup.fitToWidth=1

    detail=wb.create_sheet('成员明细')
    headers_list=['序号','加入日期','会员账号','备注信息','直属上级账号','相对层级',
                  '本人充值/建仓','本人总提现','当日提现','本人余额','本人输赢','直属人数','全部下级']
    title(detail,'成员明细 · 按加入时间从早到晚',len(headers_list))
    detail.merge_cells('A2:M2')
    detail['A2']='团队负责人：'+root['account']+'  |  含本人及全部下级：'+str(count)+'人'
    detail['A2'].font=Font(name='Microsoft YaHei',size=10,color='637C9D')
    headers(detail,4,headers_list)
    for i,r in enumerate(team,1):
        rn=i+4
        values=[i,str(r.get('joined_on') or ''),str(r['account']),str(r.get('remark') or ''),
                str(r.get('parent_account') or ''),depths[r['id']],
                int(r['stake_cents'])/100,int(r['total_withdraw_cents'])/100,
                int(r['daily_withdraw_cents'])/100,int(r['balance_cents'])/100,
                int(r['profit_cents'])/100,int(r['direct_count']),int(r['descendant_count'])]
        for col,value in enumerate(values,1):
            kind='text' if col in (2,3,4,5) else 'count' if col in (1,6,12,13) else (
                'recharge' if col==7 else 'withdraw' if col in (8,9) else
                'alert_balance' if col==10 and crosses_position_line(r) else
                'profit' if col==11 else '')
            cell(detail,rn,col,value,kind,stripe=rn%2==0)
        detail.row_dimensions[rn].height=25
    for col,width in enumerate([9,16,23,26,23,13,20,20,19,20,20,13,13],1):
        detail.column_dimensions[get_column_letter(col)].width=width
    detail.freeze_panes='D5'
    detail.auto_filter.ref=f'A4:M{max(5,4+count)}'
    detail.conditional_formatting.add(f'J5:J{4+count}',
        FormulaRule(formula=['J5>IF(G5=5000,7500,IF(G5<=10000,15000,IF(L5>=5,20000,13000)))'],
                    font=Font(name='Microsoft YaHei',bold=True,color=yellow),
                    fill=PatternFill('solid',fgColor='FFF5BF')))
    detail.print_title_rows='1:4'
    detail.sheet_properties.pageSetUpPr.fitToPage=True
    detail.page_setup.fitToWidth=1

    layers=wb.create_sheet('层级汇总')
    title(layers,'团队层级汇总 · 第0层为本人',8)
    headers(layers,4,['相对层级','人数','充值/建仓','余额','总提现','当日提现','输赢','平均余额'])
    for rn,r in enumerate(layer_rows,5):
        n=int(r['member_count'])
        values=['本人（第0层）' if r['depth']==0 else '第'+str(r['depth'])+'层',
                n,r['stake_cents']/100,r['balance_cents']/100,
                r['total_withdraw_cents']/100,r['daily_withdraw_cents']/100,
                r['profit_cents']/100,r['balance_cents']/100/n if n else 0]
        for col,value in enumerate(values,1):
            kind='count' if col==2 else 'recharge' if col==3 else 'withdraw' if col in (5,6) else 'profit' if col==7 else ''
            cell(layers,rn,col,value,kind,stripe=rn%2==0)
        layers.row_dimensions[rn].height=27
    for col,width in enumerate([22,13,21,21,21,21,21,21],1):
        layers.column_dimensions[get_column_letter(col)].width=width
    layers.freeze_panes='C5'
    layers.auto_filter.ref=f'A4:H{max(5,len(layer_rows)+4)}'
    out=io.BytesIO();wb.save(out)
    fname=quote(root['account']+'_团队数据_'+datetime.now().strftime('%Y%m%d_%H%M')+'.xlsx')
    return Response(out.getvalue(),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition':"attachment; filename=team-export.xlsx; filename*=UTF-8''"+fname})

@app.get('/api/export.xlsx')
def export_xlsx(req: Request, root_account: str | None = None):
    require(req, 'admin')
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    with engine.connect() as db:
        rows, _ = sums(active_rows(db))
    rows = filter_export_rows(rows, root_account)
    wb = Workbook()
    ws = wb.active
    ws.title = '节点数据' if root_account else '会员统计'
    ws.append(export_columns())
    for c in ws[1]:
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='294E80')
        c.alignment = Alignment(horizontal='center')
    for r in rows:
        fields = export_values(r)
        for col in (0, 2, 3, 4, 8):
            fields[col] = str(fields[col])
        ws.append(fields)
        for col in (1, 3, 4, 5, 9):
            ws.cell(ws.max_row, col).number_format = '@'
        for col in range(10, 25):
            cell = ws.cell(ws.max_row, col)
            cell.value = int(round(Decimal(fields[col-1]) * 100)) / 100
            cell.number_format = '#,##0;[Red]-#,##0;0' if col in (12, 13, 17, 18, 22, 23) else '#,##0.00;[Red]-#,##0.00;0.00'
            cell.font = Font(color='C62828' if cell.value < 0 else '111827')
    ws.freeze_panes='C2'
    ws.auto_filter.ref = ws.dimensions
    for col in ('A','B','C','D','E','F','G','H'):
        ws.column_dimensions[col].width=22 if col not in ('E',) else 36
    for i in range(10, 25):
        ws.column_dimensions[__import__('openpyxl').utils.get_column_letter(i)].width=19
    out = io.BytesIO()
    wb.save(out)
    return Response(out.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition':'attachment; filename="members-node.xlsx"' if root_account else 'attachment; filename="members-all.xlsx"'})


@app.post('/api/demo/seed')
def seed_demo(req: Request):
    raise HTTPException(410, '流星测试版不提供演示数据')


# Administrator encrypted backup payload is encrypted client-side. The server never
# receives the user's chosen backup password. This endpoint sends data only to an
# authenticated administrator and does not write to the database.
@app.get('/api/admin/backup')
def admin_backup(req: Request):
    require(req, 'admin')
    with engine.connect() as db:
        rows=[dict(x) for x in db.execute(text('SELECT * FROM members ORDER BY created_at,id')).mappings()]
        history=[dict(x) for x in db.execute(text('SELECT * FROM undo_actions ORDER BY created_at,id')).mappings()]
        logs=[dict(x) for x in db.execute(text('SELECT * FROM audit_logs ORDER BY created_at,id')).mappings()]
        withdrawals=[dict(x) for x in db.execute(text('SELECT * FROM daily_withdraw_ledger ORDER BY business_day,member_id')).mappings()]
        import_days=[x[0] for x in db.execute(text('SELECT business_day FROM daily_import_days ORDER BY business_day')).all()]
        tracking_since=db.execute(text("SELECT value FROM reporting_meta WHERE name='tracking_since'")).scalar() or current_day()
        report_snapshots=[dict(x) for x in db.execute(text('SELECT * FROM daily_group_snapshots ORDER BY business_day,group_account')).mappings()]
        report_overrides=[dict(x) for x in db.execute(text('SELECT * FROM report_manual_overrides ORDER BY business_day,group_account')).mappings()]
        team_names=[dict(x) for x in db.execute(text('SELECT * FROM team_names ORDER BY member_id')).mappings()]
        daily_fission=[dict(x) for x in db.execute(text('SELECT * FROM daily_member_fission ORDER BY business_day,member_id')).mappings()]
        withdraw_credit=[dict(x) for x in db.execute(text('SELECT * FROM daily_withdraw_credit ORDER BY business_day,member_id')).mappings()]
        business_closes=[dict(x) for x in db.execute(text('SELECT * FROM daily_business_closes ORDER BY business_day')).mappings()]
    if len(report_snapshots)>100000: raise HTTPException(409,'每日统计快照超过加密备份限额')
    if len(rows)>20000 or len(history)>500 or len(logs)>10000 or len(withdrawals)>1000000:
        raise HTTPException(409,'记录超过当前加密备份版本限制，请联系管理员进行数据库备份')
    return {'state':{'rows':rows,'history':history,'logs':logs,'withdrawals':withdrawals,'import_days':import_days,'report_snapshots':report_snapshots,'report_overrides':report_overrides,'team_names':team_names,'daily_fission':daily_fission,'withdraw_credit':withdraw_credit,'business_closes':business_closes,'tracking_since':tracking_since,'nextId':1,'version':2,'source':'production'}}



# V26: preflight duplicate reconciliation for encrypted member backups.
# No database writes occur here. Financial conflicts abort the entire restore.
def _v26_reconcile_restore_duplicates(original_state):
    import copy
    from fastapi import HTTPException

    if not isinstance(original_state, dict) or not isinstance(original_state.get('rows'), list):
        return original_state, 0
    state = copy.deepcopy(original_state)
    winners, by_account, by_id, aliases = [], {}, {}, {}
    removed = 0
    monetary = ('balance_cents', 'total_withdraw_cents', 'daily_withdraw_cents', 'stake_cents')
    for row in state['rows']:
        if not isinstance(row, dict):
            winners.append(row)
            continue
        rid = str(row.get('id', ''))
        account = str(row.get('account', '')).casefold()
        previous = by_id.get(rid)
        if previous is not None and str(previous.get('account','')).casefold() != account:
            raise HTTPException(400, '备份同一会员ID对应不同账号，请人工核对')
        target = by_account.get(account) if account else None
        if target is None:
            target = previous
        if target is None:
            winners.append(row)
            if account: by_account[account] = row
            if rid: by_id[rid] = row
            continue
        removed += 1
        if rid and rid != str(target.get('id', '')):
            aliases[rid] = str(target['id'])
        for field in monetary:
            a, b = target.get(field), row.get(field)
            if type(a) is not int or type(b) is not int:
                raise HTTPException(400, '重复账号存在无效的金额字段')
            if a and b and a != b:
                raise HTTPException(400, '重复账号 ' + str(row.get('account','')) + ' 的' + field + '金额冲突，已取消恢复，原数据未更改')
            if not a and b: target[field] = b
        p1, p2 = target.get('parent_id'), row.get('parent_id')
        if p1 and p2 and str(p1) != str(p2):
            raise HTTPException(400, '重复账号 ' + str(row.get('account','')) + ' 的上级关系冲突，已取消恢复')
        if not p1 and p2: target['parent_id'] = p2
        if not target.get('remark') and row.get('remark'): target['remark'] = row['remark']
        if row.get('joined_on') and row['joined_on'] < str(target.get('joined_on','9999-99-99')):
            target['joined_on'] = row['joined_on']
        if row.get('daily_withdraw_cents', 0) and not target.get('daily_withdraw_on'):
            target['daily_withdraw_on'] = row.get('daily_withdraw_on')
        for field in ('revision',):
            if type(row.get(field)) is int and type(target.get(field)) is int:
                target[field] = max(target[field], row[field])
        if row.get('deleted') == 0: target['deleted'] = 0
        for field, choose in (('created_at', min), ('updated_at', max)):
            if isinstance(row.get(field),str) and isinstance(target.get(field),str):
                target[field] = choose(target[field], row[field])
    if not removed:
        return state, 0

    def canonical(mid):
        x = str(mid)
        seen = set()
        while x in aliases:
            if x in seen: raise HTTPException(400, '重复会员ID映射发生循环，停止恢复')
            seen.add(x)
            x = aliases[x]
        return x

    for row in winners:
        if isinstance(row, dict) and row.get('parent_id') is not None:
            row['parent_id'] = canonical(row['parent_id'])
    state['rows'] = winners

    # Preserve all linked history. Identical colliding records are merged;
    # genuinely different monetary records are rejected, never discarded.
    related = (
        ('withdrawals', ('member_id', 'business_day'), ('amount_cents',)),
        ('withdraw_credit', ('member_id', 'business_day'), ('credited_cents',)),
        ('daily_fission', ('member_id', 'business_day'), ('ratio_bp',)),
        ('team_names', ('member_id',), ('name',)),
    )
    for name, key_fields, protected_fields in related:
        values = state.get(name, [])
        if not isinstance(values, list): continue
        seen, kept = {}, []
        for item in values:
            if not isinstance(item,dict):
                kept.append(item)
                continue
            if 'member_id' in item: item['member_id'] = canonical(item['member_id'])
            key = tuple(str(item.get(k)) for k in key_fields)
            if key in seen:
                prior = seen[key]
                if any(prior.get(k) != item.get(k) for k in protected_fields):
                    raise HTTPException(400, '重复会员关联的' + name + '记录金额或内容冲突，恢复已停止')
                # Keep a nonempty settlement date and freshest metadata.
                for k,v in item.items():
                    if k not in protected_fields and k not in key_fields and v is not None:
                        if prior.get(k) is None or (isinstance(v,str) and isinstance(prior.get(k),str) and v > prior[k]):
                            prior[k] = v
            else:
                seen[key] = item
                kept.append(item)
        state[name] = kept

    # Only discard truly identical duplicated audit/undo rows.
    for name in ('logs', 'history'):
        values = state.get(name, [])
        if not isinstance(values,list): continue
        seen, kept = {}, []
        for item in values:
            if not isinstance(item,dict):
                kept.append(item)
                continue
            key = str(item.get('id'))
            if key in seen:
                if seen[key] != item:
                    raise HTTPException(400, '备份' + name + '有相同ID但内容不同的记录，恢复已停止')
            else:
                seen[key] = item
                kept.append(item)
        state[name] = kept

    # Other unique-key snapshots: remove only exact copies.
    for name, fields in (
        ('report_snapshots', ('business_day', 'group_account')),
        ('report_overrides', ('business_day', 'group_account')),
        ('business_closes', ('business_day',)),
    ):
        values = state.get(name, [])
        if not isinstance(values,list): continue
        seen, kept = {}, []
        for item in values:
            if not isinstance(item,dict):
                kept.append(item)
                continue
            key = tuple(str(item.get(k)) for k in fields)
            if key in seen:
                if seen[key] != item:
                    raise HTTPException(400, '备份' + name + '存在同键不同内容，恢复已停止')
            else:
                seen[key] = item
                kept.append(item)
        state[name] = kept
    return state, removed

@app.post('/api/admin/restore')
def admin_restore(req: Request, data: dict):
    actor=require(req,'admin',True).get('username','')
    if data.get('confirm')!='RESTORE_WITH_BACKUP':
        raise HTTPException(400,'请先确认恢复操作')
    state=data.get('state')
    if not isinstance(state,dict): raise HTTPException(400,'备份结构无效')
    state, duplicate_members_removed = _v26_reconcile_restore_duplicates(state)
    rows=state.get('rows');history=state.get('history');logs=state.get('logs')
    if not all(isinstance(x,list) for x in (rows,history,logs)):
        raise HTTPException(400,'备份缺少会员、操作记录')
    if len(rows)>20000 or len(history)>500 or len(logs)>10000:
        raise HTTPException(400,'备份记录数超出安全限制')
    withdrawals=state.get('withdrawals',[])
    import_days=state.get('import_days',[])
    tracking_since=state.get('tracking_since',current_day())
    report_snapshots=state.get('report_snapshots',[])
    report_overrides=state.get('report_overrides',[])
    team_names=state.get('team_names',[])
    daily_fission=state.get('daily_fission',[])
    withdraw_credit=state.get('withdraw_credit',[])
    business_closes=state.get('business_closes',[])
    if not isinstance(withdraw_credit,list) or len(withdraw_credit)>1000000 or not isinstance(business_closes,list) or len(business_closes)>50000:
        raise HTTPException(400,'提现结算历史格式不正确')
    for x in withdraw_credit:
        if not isinstance(x,dict) or not all(k in x for k in ('member_id','business_day','credited_cents','settled_at')) or type(x['credited_cents']) is not int or x['credited_cents']<0:
            raise HTTPException(400,'提现结算字段无效')
        valid_date(x['business_day'])
    for x in business_closes:
        if not isinstance(x,dict) or not all(k in x for k in ('business_day','closed_at','source_captured_at','quality')):
            raise HTTPException(400,'日结字段无效')
        valid_date(x['business_day'])
    if not isinstance(daily_fission,list) or len(daily_fission)>1000000:raise HTTPException(400,'裂变历史备份格式不正确')
    seen_fission=set()
    for x in daily_fission:
        if not isinstance(x,dict) or not all(k in x for k in ('member_id','business_day','ratio_bp','captured_at')):raise HTTPException(400,'裂变快照字段无效')
        valid_date(x['business_day'])
        if type(x['ratio_bp']) is not int or x['ratio_bp']<0 or x['ratio_bp']>10000:raise HTTPException(400,'裂变比率数据无效')
        if not isinstance(x['captured_at'],str) or len(x['captured_at'])>60:raise HTTPException(400,'裂变采集时间无效')
        key=(str(x['member_id']),x['business_day'])
        if key in seen_fission:raise HTTPException(400,'裂变历史重复')
        seen_fission.add(key)
    if not isinstance(team_names,list) or len(team_names)>20000:raise HTTPException(400,'团队名称备份无效')
    for label in team_names:
        if not isinstance(label,dict) or not all(k in label for k in ('member_id','name','updated_at')) or not isinstance(label['name'],str) or len(label['name'])>20:
            raise HTTPException(400,'团队名称备份格式错误')
    if not isinstance(report_overrides,list) or len(report_overrides)>100000:
        raise HTTPException(400,'手动报表修正记录无效')
    seen_overrides=set()
    for fix in report_overrides:
        if not isinstance(fix,dict) or not all(k in fix for k in ('business_day','group_account','values_json','operator','updated_at')):
            raise HTTPException(400,'手动报表修正字段缺失')
        valid_date(fix['business_day'])
        if fix['group_account'] not in ('01','02','03','06','08') or (fix['business_day'],fix['group_account']) in seen_overrides:
            raise HTTPException(400,'手动报表修正分组重复或非法')
        seen_overrides.add((fix['business_day'],fix['group_account']))
        try: parsed=json.loads(fix['values_json'])
        except (ValueError,TypeError):raise HTTPException(400,'修正内容不是有效JSON')
        fields=('member_count','new_count','new_stake_cents','withdraw_cents','balance_cents')
        if set(parsed)!=set(fields) or any(type(parsed[k]) is not int or parsed[k]<0 or parsed[k]>10**16 for k in fields) or parsed['new_count']>parsed['member_count']:
            raise HTTPException(400,'手动修正数字不合法')
        if len(fix['updated_at'])>60 or len(fix['operator'])>64:raise HTTPException(400,'手动修正元数据过长')
    if not isinstance(report_snapshots,list) or len(report_snapshots)>100000: raise HTTPException(400,'每日统计快照格式不正确')
    seen_snapshots=set()
    for item in report_snapshots:
        if not isinstance(item,dict) or not all(k in item for k in ('business_day','group_account','member_count','new_count','new_stake_cents','withdraw_cents','balance_cents','captured_at')):
            raise HTTPException(400,'每日统计快照字段不全')
        valid_date(item['business_day'])
        g=item['group_account']
        if not isinstance(g,str) or len(g)>64:raise HTTPException(400,'快照分组无效')
        key=(item['business_day'],g)
        if key in seen_snapshots:raise HTTPException(400,'快照日期与分组重复')
        seen_snapshots.add(key)
        for field in ('member_count','new_count','new_stake_cents','withdraw_cents','balance_cents'):
            if type(item[field]) is not int or item[field]<0 or item[field]>10**16:raise HTTPException(400,'快照数字无效')
        if not isinstance(item['captured_at'],str) or len(item['captured_at'])>60:raise HTTPException(400,'快照时间无效')
    if not isinstance(withdrawals,list) or not isinstance(import_days,list) or len(withdrawals)>1000000:
        raise HTTPException(400,'提现历史备份格式不正确')
    try:
        valid_date(tracking_since)
        for d in import_days:valid_date(d)
        seen_hist=set()
        for x in withdrawals:
            if not isinstance(x,dict) or not all(k in x for k in ('member_id','business_day','amount_cents')):
                raise ValueError('提现历史字段缺失')
            valid_date(x['business_day'])
            if type(x['amount_cents']) is not int or x['amount_cents']<0 or x['amount_cents']>10**16:
                raise ValueError('提现历史金额错误')
            key=(x['member_id'],x['business_day'])
            if key in seen_hist:raise ValueError('提现历史重复')
            seen_hist.add(key)
    except (TypeError,ValueError,KeyError) as e:
        raise HTTPException(400,'提现历史备份无效：'+str(e))
    by_id={};seen_account=set()
    fields=('id','account','joined_on','parent_id','balance_cents','total_withdraw_cents',
            'daily_withdraw_cents','stake_cents','daily_withdraw_on','remark','revision',
            'deleted','created_at','updated_at')
    if any(not isinstance(x,dict) for x in rows):raise HTTPException(400,'会员记录结构不正确')
    for row in rows:
        if any(k not in row for k in fields): raise HTTPException(400,'备份缺少会员字段')
        ident=str(row['id']);account=str(row['account'])
        if len(ident)>64 or not ident or ident in by_id:
            raise HTTPException(400,'会员ID重复或无效')
        if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,64}',account) or account.casefold() in seen_account:
            raise HTTPException(400,'会员账号格式错误或重复')
        seen_account.add(account.casefold())
        valid_date(row['joined_on'])
        if not isinstance(row['remark'],str) or len(row['remark'])>20:raise HTTPException(400,'备注不合法')
        for k in ('balance_cents','total_withdraw_cents','daily_withdraw_cents','stake_cents'):
            v=row[k]
            if type(v) is not int or v<0 or v>10**16:raise HTTPException(400,'备份金额不合法')
        if type(row['revision']) is not int or row['revision']<1 or row['revision']>10**9:
            raise HTTPException(400,'会员版本号不合法')
        if row['deleted'] not in (0,1):raise HTTPException(400,'会员删除状态不合法')
        if row['daily_withdraw_on'] is not None:valid_date(row['daily_withdraw_on'])
        if not isinstance(row['created_at'],str) or not isinstance(row['updated_at'],str):
            raise HTTPException(400,'时间字段不合法')
        by_id[ident]=row
    for row in rows:
        parent=row['parent_id'];ident=str(row['id'])
        if parent is not None and str(parent) not in by_id:raise HTTPException(400,'上级会员记录缺失')
        seen=set();cur=ident
        while cur is not None:
            if cur in seen:raise HTTPException(400,'会员层级存在循环')
            if cur not in by_id:raise HTTPException(400,'上级会员记录缺失')
            seen.add(cur)
            parent=by_id[cur]['parent_id']
            cur=str(parent) if parent is not None else None
    for item in daily_fission:
        if str(item['member_id']) not in by_id:raise HTTPException(400,'裂变快照会员不存在')
    for label in team_names:
        if str(label['member_id']) not in by_id:raise HTTPException(400,'团队名称对应的会员不存在')
    for x in withdrawals:
        if str(x['member_id']) not in by_id:
            raise HTTPException(400,'历史提现对应会员不存在')
    # Atomic replace: if any validation/insert fails, all prior rows are rolled back.
    with engine.begin() as db:
        write_lock(db)
        # Retain current nonblank member notes when an older backup omits them.
        previous_remarks={str(r['account']).casefold():r['remark'] for r in
          db.execute(text("SELECT account,remark FROM members WHERE deleted=0 AND remark<>''")).mappings()}
        for backup_member in rows:
            if not backup_member['remark']:
                backup_member['remark']=previous_remarks.get(str(backup_member['account']).casefold(),'')
        db.execute(text('DELETE FROM import_jobs'))
        db.execute(text('DELETE FROM daily_withdraw_credit'))
        db.execute(text('DELETE FROM daily_business_closes'))
        db.execute(text('DELETE FROM daily_withdraw_ledger'))
        db.execute(text('DELETE FROM daily_import_days'))
        db.execute(text('DELETE FROM daily_group_snapshots'))
        db.execute(text('DELETE FROM report_manual_overrides'))
        preserved_team_names=v33_capture_team_names(db)
        db.execute(text('DELETE FROM team_names'))
        db.execute(text('DELETE FROM daily_member_fission'))
        db.execute(text('DELETE FROM undo_actions'))
        db.execute(text('DELETE FROM audit_logs'))
        # Delete children before parents to avoid immediate self-FK enforcement.
        remaining={str(r['id']):r for r in rows}
        present=db.execute(text('SELECT id,parent_id FROM members')).mappings().all()
        present_by={r['id']:r['parent_id'] for r in present}
        while present_by:
            leaves=[mid for mid in present_by if mid not in set(p for p in present_by.values() if p)]
            if not leaves:raise HTTPException(409,'当前会员层级不合法，停止恢复')
            for mid in leaves:
                db.execute(text('DELETE FROM members WHERE id=:id'),{'id':mid})
                present_by.pop(mid)
        inserted=set()
        while remaining:
            ready=[(mid,r) for mid,r in remaining.items() if r['parent_id'] is None or str(r['parent_id']) in inserted]
            if not ready:raise HTTPException(400,'备份关系异常')
            for mid,row in ready:
                db.execute(text('''INSERT INTO members(id,account,joined_on,parent_id,balance_cents,
                         total_withdraw_cents,daily_withdraw_cents,stake_cents,daily_withdraw_on,
                         remark,revision,deleted,created_at,updated_at)
                         VALUES (:id,:account,:joined_on,:parent_id,:balance_cents,
                         :total_withdraw_cents,:daily_withdraw_cents,:stake_cents,:daily_withdraw_on,
                         :remark,:revision,:deleted,:created_at,:updated_at)'''),
                         {k:row[k] for k in fields})
                inserted.add(mid);remaining.pop(mid)
        if not withdrawals:
            # Legacy V11 backup: preserve the last visible day only, never fabricate other days.
            for r in rows:
                if r['daily_withdraw_on'] and r['daily_withdraw_cents']:
                    set_daily_ledger(db,r['id'],r['daily_withdraw_on'],r['daily_withdraw_cents'])
        else:
            for item in withdrawals:
                set_daily_ledger(db,item['member_id'],item['business_day'],item['amount_cents'])
        # V20 backup carries credited/closed state; V19 backup totals already included all existing ledger amounts.
        if 'withdraw_credit' in state:
            for x in withdraw_credit:
                db.execute(text('''INSERT INTO daily_withdraw_credit(member_id,business_day,credited_cents,settled_at)
                 VALUES (:member_id,:business_day,:credited_cents,:settled_at)'''),x)
        else:
            for x in db.execute(text('SELECT member_id,business_day,amount_cents FROM daily_withdraw_ledger')).mappings().all():
                db.execute(text('''INSERT INTO daily_withdraw_credit(member_id,business_day,credited_cents,settled_at)
                   VALUES (:m,:d,:a,NULL) ON CONFLICT(member_id,business_day) DO NOTHING'''),
                   {'m':x['member_id'],'d':x['business_day'],'a':x['amount_cents']})
        for x in business_closes:
            db.execute(text('''INSERT INTO daily_business_closes(business_day,closed_at,source_captured_at,quality)
                 VALUES (:business_day,:closed_at,:source_captured_at,:quality)'''),x)
        for dt in sorted(set(import_days)):
            db.execute(text('INSERT INTO daily_import_days(business_day,recorded_at) VALUES (:d,:t)'),
                       {'d':dt,'t':utc_now()})
        for item in daily_fission:
            db.execute(text('INSERT INTO daily_member_fission (member_id,business_day,ratio_bp,captured_at) VALUES (:member_id,:business_day,:ratio_bp,:captured_at)'),item)
        for label in team_names:
            db.execute(text('INSERT INTO team_names(member_id,name,updated_at) VALUES (:member_id,:name,:updated_at)'),label)
        v33_restore_team_names(db,preserved_team_names)
        for item in report_overrides:
            db.execute(text('''INSERT INTO report_manual_overrides (business_day,group_account,values_json,operator,updated_at) VALUES (:business_day,:group_account,:values_json,:operator,:updated_at)'''),item)
        for item in report_snapshots:
            db.execute(text('''INSERT INTO daily_group_snapshots (business_day,group_account,member_count,new_count,new_stake_cents,withdraw_cents,balance_cents,captured_at) VALUES (:business_day,:group_account,:member_count,:new_count,:new_stake_cents,:withdraw_cents,:balance_cents,:captured_at)'''),item)
        db.execute(text("UPDATE reporting_meta SET value=:v WHERE name='tracking_since'"),{'v':tracking_since})
        # Operation logs are restored as historical records, retaining audit chronology.
        for row in logs:
            if not isinstance(row,dict) or not all(k in row for k in ('id','event','detail','created_at')):
                raise HTTPException(400,'日志结构不合法')
            db.execute(text('INSERT INTO audit_logs(id,event,detail,created_at) VALUES (:id,:event,:detail,:created_at)'),
                       {k:row[k] for k in ('id','event','detail','created_at')})
        for row in history:
            ks=('id','operator','event','label','changes_json','created_at','undone','undone_at')
            if not isinstance(row,dict) or not all(k in row for k in ks):
                raise HTTPException(400,'撤回历史结构不合法')
            db.execute(text('''INSERT INTO undo_actions(id,operator,event,label,changes_json,created_at,undone,undone_at)
                VALUES (:id,:operator,:event,:label,:changes_json,:created_at,:undone,:undone_at)'''),
                {k:row[k] for k in ks})
        audit(db,'restore',{'members':len(rows),'logs':len(logs),'backup_origin':state.get('source','unknown')},actor)
    return {'ok':True,'members':len(rows),'logs':len(logs),'duplicate_members_removed':duplicate_members_removed}

# V14: restore members from the complete old-version CSV/XLSX export, distinct
# from the day-to-day finance import. No mutation occurs on preview.

def legacy_account(value):
    if value is None: return ''
    if isinstance(value,int): return str(value)
    if isinstance(value,float):
        if not value.is_integer(): raise ValueError('会员账号不能是小数')
        return str(int(value))
    return str(value).strip()


def legacy_xlsx_account(cell):
    v=cell.value
    if isinstance(v,(int,float)) and float(v).is_integer():
        fmt=str(cell.number_format or '')
        if re.fullmatch(r'0{2,64}',fmt): return str(int(v)).zfill(len(fmt))
    return legacy_account(v)


def legacy_cents(value,field):
    if value is None or str(value).strip()=='':return 0
    v=str(value).strip().replace(',','').replace('，','').replace('¥','').replace('￥','')
    try:return cents(v)
    except HTTPException as exc:raise ValueError(field+'金额格式不正确：'+str(value)) from exc


def parse_legacy_full_export(payload,filename):
    import os as _os
    ext=_os.path.splitext(filename.lower())[1]
    if ext in ('.xlsx','.xlsm'):
        try:
            wb=load_workbook(io.BytesIO(payload),read_only=True,data_only=True)
            ws=wb.active
            iterator=ws.iter_rows()
            first=next(iterator,None)
            if not first:raise ValueError('空Excel文件')
            heads=[str(x.value or '').strip().replace('\ufeff','') for x in first]
            lines=[[legacy_xlsx_account(row[0]) if col==0 else cell.value for col,cell in enumerate(row)] for row in iterator]
            wb.close()
        except (OSError,KeyError,ValueError) as exc:raise HTTPException(400,'Excel解析失败：'+str(exc))
    elif ext in ('.csv','.txt'):
        try:
            try:src=payload.decode('utf-8-sig')
            except UnicodeDecodeError:src=payload.decode('gb18030')
            reader=csv.reader(io.StringIO(src))
            heads=[x.strip().replace('\ufeff','') for x in next(reader)]
            lines=list(reader)
        except (UnicodeDecodeError,StopIteration,csv.Error) as exc:raise HTTPException(400,'CSV解析失败：'+str(exc))
    else:raise HTTPException(400,'请上传旧版导出的全员CSV或Excel（加密备份请使用恢复加密备份）')
    col={k:i for i,k in enumerate(heads)}
    def idx(*names):
        for name in names:
            if name in col:return col[name]
        return None
    fieldmap={
        'account':idx('会员账号','账号'),
        'joined_on':idx('加入日期','入会日期'),
        'parent':idx('直属上级账号','直属上级','上级账号','推荐人账号'),
        'remark':idx('备注','备注信息'),
        'stake':idx('本人建仓资金','建仓资金','本人建仓'),
        'balance':idx('本人余额','余额','当前余额'),
        'total':idx('本人总提现','累计提现','总提现','累计总提现'),
        'daily':idx('本人当日提现','当日提现'),
    }
    if any(fieldmap[k] is None for k in ('account','joined_on','parent','stake')):
        raise HTTPException(400,'这不是完整会员导出表：需要会员账号、加入日期、直属上级、本人建仓。逐层汇总表不能用于恢复会员关系')
    if len(lines)>20000:raise HTTPException(400,'恢复会员最多20000条')
    parsed=[];seen=set()
    for no,line in enumerate(lines,start=2):
        if not any(str(x or '').strip() for x in line):continue
        def val(k):
            i=fieldmap[k]
            return line[i] if i is not None and i<len(line) else None
        try:
            account=legacy_account(val('account'))
            if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,64}',account):raise ValueError('会员账号无效')
            if account.casefold() in seen:raise ValueError('账号重复：'+account)
            seen.add(account.casefold())
            joined=val('joined_on')
            if isinstance(joined,(datetime,date)):joined=joined.date().isoformat() if isinstance(joined,datetime) else joined.isoformat()
            joined=str(joined or '').strip()
            valid_date(joined)
            parent=legacy_account(val('parent'))
            if parent in ('—','-','无','根节点','None','null'):parent=''
            remark=str(val('remark') or '').strip()
            if len(remark)>20:raise ValueError('备注超过20字')
            if any(ord(ch)<32 for ch in remark):raise ValueError('备注包含非法字符')
            item={'account':account,'joined_on':joined,'parent_account':parent,'remark':remark}
            for key,name in [('stake','建仓'),('balance','余额'),('total','累计提现'),('daily','当日提现')]:
                item[key+'_cents']=legacy_cents(val(key),name)
            parsed.append(item)
        except (HTTPException,ValueError) as exc:
            detail=exc.detail if isinstance(exc,HTTPException) else str(exc)
            raise HTTPException(400,f'第{no}行：{detail}')
    if not parsed:raise HTTPException(400,'没有识别到可恢复的会员')
    lookup={r['account'].casefold():r for r in parsed}
    for item in parsed:
        p=item['parent_account']
        if p and p.casefold() not in lookup:
            raise HTTPException(400,f'会员 {item["account"]} 的上级账号 {p} 不在此文件中，请导入完整全员文件')
        seen_parents=set();cur=item
        while cur.get('parent_account'):
            key=cur['account'].casefold()
            if key in seen_parents:raise HTTPException(400,'上下级关系存在循环：'+item['account'])
            seen_parents.add(key)
            cur=lookup[cur['parent_account'].casefold()]
    return parsed


@app.post('/api/admin/legacy/preview')
async def legacy_preview(req: Request, upload: UploadFile = File(...)):
    actor=require(req,'admin',True)
    content=await upload.read(12*1024*1024+1)
    if len(content)>12*1024*1024:raise HTTPException(400,'旧版全员文件不得超过12MB')
    parsed=parse_legacy_full_export(content,upload.filename or '')
    with engine.begin() as db:
        write_lock(db)
        existing=active_rows(db)
        stamp=roster_stamp(existing)
        jobid=str(uuid.uuid4())
        db.execute(text('INSERT INTO legacy_restore_jobs(id,rows_json,source_stamp,created_at) VALUES (:i,:r,:s,:t)'),{
            'i':jobid,'r':json.dumps(parsed,ensure_ascii=False),'s':stamp,'t':utc_now()})
    return {'job_id':jobid,'members':len(parsed),'existing_members':len(existing),
            'roots':sum(1 for x in parsed if not x['parent_account']),
            'amounts':{k:sum(int(x[k+'_cents']) for x in parsed)/100 for k in ('stake','balance','total','daily')},
            'sample':[{'account':x['account'],'parent':x['parent_account'],'date':x['joined_on'],'remark':x['remark']} for x in parsed[:8]],
            'notice':'恢复旧版全员资料会替换当前会员及关系；不会凭空恢复旧版缺失的逐日流水或撤回记录。CSV/Excel只保留本人金额，旧表中的各层汇总不会重复导入。旧文件当日提现按本次导入的北京时间日期挂账，请核对文件是否是今日导出。'}


@app.post('/api/admin/legacy/{jobid}/confirm')
def legacy_confirm(jobid:str,req:Request,payload:dict):
    actor=require(req,'admin',True).get('username','')
    if payload.get('confirm')!='确认覆盖旧会员数据':raise HTTPException(400,'请输入正确的二次确认文字')
    with engine.begin() as db:
        write_lock(db)
        job=db.execute(text('SELECT * FROM legacy_restore_jobs WHERE id=:id'),{'id':jobid}).mappings().first()
        if not job:raise HTTPException(404,'恢复预览已过期，请重新选择文件')
        if datetime.now(timezone.utc)-datetime.fromisoformat(job['created_at'])>timedelta(minutes=30):
            raise HTTPException(409,'预览已超过30分钟，请重新上传')
        existing=active_rows(db)
        if roster_stamp(existing)!=job['source_stamp']:
            raise HTTPException(409,'其他管理员已修改会员资料，请重新预览，避免覆盖新修改')
        parsed=json.loads(job['rows_json'])
        previous_remarks={str(r['account']).casefold():r['remark'] for r in existing if r.get('remark')}
        for imported in parsed:
            if not imported['remark']:
                imported['remark']=previous_remarks.get(str(imported['account']).casefold(),'')
        now=utc_now();today=current_day()
        byaccount={x['account'].casefold():str(uuid.uuid4()) for x in parsed}
        # Delete data from child to parent within a single atomic transaction.
        db.execute(text('DELETE FROM daily_withdraw_credit'))
        db.execute(text('DELETE FROM daily_business_closes'))
        db.execute(text('DELETE FROM daily_withdraw_ledger'))
        db.execute(text('DELETE FROM daily_import_days'))
        db.execute(text('DELETE FROM daily_group_snapshots'))
        db.execute(text('DELETE FROM report_manual_overrides'))
        preserved_team_names=v33_capture_team_names(db)
        db.execute(text('DELETE FROM team_names'))
        db.execute(text('DELETE FROM daily_member_fission'))
        db.execute(text('DELETE FROM import_jobs'))
        db.execute(text('DELETE FROM undo_actions'))
        present=db.execute(text('SELECT id,parent_id FROM members')).mappings().all()
        remaining={r['id']:r['parent_id'] for r in present}
        while remaining:
            parents={v for v in remaining.values() if v is not None}
            leaves=[mid for mid in remaining if mid not in parents]
            if not leaves:raise HTTPException(409,'现有会员关系异常，已停止导入且未改动数据')
            for mid in leaves:
                db.execute(text('DELETE FROM members WHERE id=:id'),{'id':mid})
                remaining.pop(mid)
        # Topological insert so every parent exists before the child.
        waiting={x['account'].casefold():x for x in parsed};inserted=set()
        while waiting:
            ready=[(key,row) for key,row in waiting.items() if not row['parent_account'] or row['parent_account'].casefold() in inserted]
            if not ready:raise HTTPException(400,'备份上下级关系不能恢复')
            for key,row in ready:
                parent=row['parent_account'].casefold() if row['parent_account'] else None
                daily=row['daily_cents']
                db.execute(text('''INSERT INTO members(id,account,joined_on,parent_id,stake_cents,balance_cents,
                      total_withdraw_cents,daily_withdraw_cents,daily_withdraw_on,remark,created_at,updated_at)
                      VALUES (:id,:account,:joined,:parent,:stake,:balance,:total,:daily,:d,:remark,:created,:created)'''),
                      {'id':byaccount[key],'account':row['account'],'joined':row['joined_on'],
                       'parent':byaccount[parent] if parent else None,'stake':row['stake_cents'],
                       'balance':row['balance_cents'],'total':row['total_cents'],'daily':daily,
                       'd':today if daily else None,'remark':row['remark'],'created':now})
                if daily:
                    set_daily_ledger(db,byaccount[key],today,daily)
                    db.execute(text('''INSERT INTO daily_withdraw_credit(member_id,business_day,credited_cents,settled_at)
                       VALUES (:m,:d,:a,NULL)'''),{'m':byaccount[key],'d':today,'a':daily})
                inserted.add(key);waiting.pop(key)
        v33_restore_team_names(db,preserved_team_names)
        db.execute(text("UPDATE reporting_meta SET value=:d WHERE name='tracking_since'"),{'d':today})
        db.execute(text('DELETE FROM legacy_restore_jobs'))
        audit(db,'legacy_restore',{'count':len(parsed),'previous_count':len(existing)},actor)
    return {'ok':True,'members':len(parsed)}

# V15 report extension: additive, read-provenance-aware daily group snapshots.
# Never alter member balances or relationships while building reports.
REPORT_GROUPS=('01','02','03','06','08')
REPORT_ALL='__ALL__'
REPORT_COLS=('business_day','group_account','member_count','new_count','new_stake_cents',
             'withdraw_cents','balance_cents','captured_at')


def report_rows_today(db, day):
    raw=active_rows(db)
    rows,_=sums(raw)
    groups={g:{'business_day':day,'group_account':g,'member_count':0,'new_count':0,
              'new_stake_cents':0,'withdraw_cents':0,'balance_cents':0,'captured_at':utc_now()}
            for g in (*REPORT_GROUPS, REPORT_ALL)}
    for r in rows:
        g=r['group_account']
        if g not in groups:
            groups[g]={'business_day':day,'group_account':g,'member_count':0,'new_count':0,
                       'new_stake_cents':0,'withdraw_cents':0,'balance_cents':0,'captured_at':utc_now()}
        for target in (groups[g],groups[REPORT_ALL]):
            target['member_count']+=1
            target['balance_cents']+=int(r['balance_cents'])
            target['withdraw_cents']+=int(r['daily_withdraw_cents'])
            if r['joined_on']==day:
                target['new_count']+=1
                target['new_stake_cents']+=int(r['stake_cents'])
    return groups


def store_live_report_snapshots(db, data):
    for r in data.values():
        db.execute(text('''INSERT INTO daily_group_snapshots
             (business_day,group_account,member_count,new_count,new_stake_cents,withdraw_cents,balance_cents,captured_at)
             VALUES (:business_day,:group_account,:member_count,:new_count,:new_stake_cents,:withdraw_cents,:balance_cents,:captured_at)
             ON CONFLICT (business_day,group_account) DO UPDATE SET
             member_count=excluded.member_count,new_count=excluded.new_count,
             new_stake_cents=excluded.new_stake_cents,withdraw_cents=excluded.withdraw_cents,
             balance_cents=excluded.balance_cents,captured_at=excluded.captured_at'''),r)


def report_metric(row, previous=None, monthly_known=None, monthly_partial=0, status='历史采样'):
    if row is None:return None
    n=int(row['member_count']); stake=int(row['new_stake_cents']); withdrawal=int(row['withdraw_cents'])
    difference=(n-int(previous['member_count'])) if previous is not None else None
    # 泡沫：今日余额减去昨日最终已知余额；有增有减，保持正负号。
    betting=int(row['balance_cents'])-int(previous['balance_cents']) if previous is not None else None
    fee=(withdrawal+5)//10
    return {'business_day':row['business_day'],'group_account':row['group_account'],
        'new_count':int(row['new_count']),'member_count':n,'count_change':difference,
        'new_stake_cents':stake,'withdraw_cents':withdrawal,'fee_cents':fee,
        'profit_cents':stake-withdrawal,'betting_cents':betting,
        'balance_cents':int(row['balance_cents']),
        'avg_balance_cents':int(Decimal(row['balance_cents'])/n) if n else 0,
        'yesterday_balance_cents':int(previous['balance_cents']) if previous is not None else None,
        'bubble_change_cents':int(row['balance_cents'])-int(previous['balance_cents']) if previous is not None else None,
        'monthly_profit_cents':monthly_known,'monthly_partial_cents':monthly_partial,
        'captured_at':row['captured_at'],'status':status,
        'close_verified':False}


def parse_report_request(month=None, group=None):
    today=current_day()
    month=month or today[:7]
    if not re.fullmatch(r'20\d{2}-(?:0[1-9]|1[0-2])', month or ''):
        raise HTTPException(400,'月份格式应为YYYY-MM')
    if month>today[:7]:raise HTTPException(400,'不能查看未来月份')
    group=group or 'all'
    if group!='all' and group not in REPORT_GROUPS:
        raise HTTPException(400,'请选择01、02、03、06、08或全盘')
    return today,month,group


def build_report(db, month=None, group='all', selected_day=None):
    today,month,group=parse_report_request(month,group)
    if selected_day:
        try: selected=date.fromisoformat(selected_day)
        except (TypeError,ValueError): raise HTTPException(400,'日期格式应为YYYY-MM-DD')
        if selected.isoformat()!=selected_day or selected_day>today or selected_day[:7]!=month:
            raise HTTPException(400,'选择的日期必须属于指定月份且不晚于今天')
    else: selected_day=today if month==today[:7] else None
    # Close any previous day once, before sampling the current day.
    settle_past_days(db,today)
    current=report_rows_today(db,today)
    store_live_report_snapshots(db,current)
    query_end=today if month==today[:7] else (date.fromisoformat(month+'-01').replace(day=28)+timedelta(days=4)).replace(day=1).isoformat()
    start=month+'-01'
    # Includes preceding day for accurate member/balance comparison where snapshots exist.
    previous=(date.fromisoformat(start)-timedelta(days=1)).isoformat()
    end=today if month==today[:7] else (date.fromisoformat(query_end)-timedelta(days=1)).isoformat()
    closes={x['business_day']:dict(x) for x in db.execute(text('SELECT * FROM daily_business_closes WHERE business_day>=:s AND business_day<=:e'),{'s':previous,'e':end}).mappings()}
    all_raw=db.execute(text('''SELECT * FROM daily_group_snapshots WHERE business_day>=:start AND business_day<=:end
                ORDER BY business_day,group_account'''),{'start':previous,'end':end}).mappings().all()
    snapshots={(r['business_day'],r['group_account']):dict(r) for r in all_raw}
    correction_rows=db.execute(text('''SELECT business_day,group_account,values_json,operator,updated_at
      FROM report_manual_overrides WHERE business_day>=:s AND business_day<=:e'''),{'s':previous,'e':end}).mappings().all()
    overrides={(r['business_day'],r['group_account']):dict(r) for r in correction_rows}
    def apply_override(raw):
        if raw is None:return None
        fixed=overrides.get((raw['business_day'],raw['group_account']))
        if not fixed:return dict(raw)
        values=json.loads(fixed['values_json'])
        return {**dict(raw),**values,'is_manual':True,'manual_operator':fixed['operator'],
                'manual_updated_at':fixed['updated_at']}
    labels=list(REPORT_GROUPS)
    extra=[g for g in current if g not in (*REPORT_GROUPS,REPORT_ALL)]
    if extra:labels.append('其他')
    labels.append(REPORT_ALL)
    dates=[];day=date.fromisoformat(start);last=date.fromisoformat(end)
    while day<=last:
        dates.append(day.isoformat());day+=timedelta(days=1)
    def raw_for(day_key,selected_group):
        # V21: every today's report row MUST share the same current member data as /api/tree.
        # Historical manual corrections are deliberately not applied to active business day:
        # otherwise a prior correction masks the latest import in both table and charts.
        if day_key == today:
            if selected_group == '其他':
                extras=[dict(x) for g,x in current.items() if g not in (*REPORT_GROUPS,REPORT_ALL)]
                if not extras: return None
                return {**extras[0],**{k:sum(int(x[k]) for x in extras) for k in
                  ('member_count','new_count','new_stake_cents','withdraw_cents','balance_cents')},
                  'group_account':'其他'}
            return dict(current[selected_group]) if selected_group in current else None
        if selected_group=='其他':
            extras=[apply_override(x) for (d,g),x in snapshots.items() if d==day_key and g not in (*REPORT_GROUPS,REPORT_ALL)]
            if not extras:return None
            return {**extras[0],**{k:sum(int(x[k]) for x in extras) for k in ('member_count','new_count','new_stake_cents','withdraw_cents','balance_cents')},'group_account':'其他'}
        if selected_group==REPORT_ALL:
            original=snapshots.get((day_key,REPORT_ALL))
            # A manually corrected child group must update the grand total, without
            # double-counting any member. All group rows are disjoint root teams.
            changed=any(d==day_key for d,g in overrides)
            if changed and original:
                groups=[apply_override(raw) for (d,g),raw in snapshots.items() if d==day_key and g!=REPORT_ALL]
                if not groups:return dict(original)
                return {**dict(original),**{k:sum(int(x[k]) for x in groups) for k in ('member_count','new_count','new_stake_cents','withdraw_cents','balance_cents')},'is_manual':True}
            return apply_override(original)
        return apply_override(snapshots.get((day_key,selected_group)))
    def metric_for(day_key,selected_group):
        raw=raw_for(day_key,selected_group)
        if not raw:return None
        prev_date=(date.fromisoformat(day_key)-timedelta(days=1)).isoformat()
        prev=raw_for(prev_date,selected_group)
        same_month=[d for d in dates if d<=day_key]
        partial=sum(int(raw_for(d,selected_group)['new_stake_cents'])-int(raw_for(d,selected_group)['withdraw_cents']) for d in same_month if raw_for(d,selected_group))
        complete=all(raw_for(d,selected_group) is not None for d in same_month)
        status='今日实时' if day_key==today else ('历史已结算（最近上传值，非精确24点）' if day_key in closes else '历史采样（非24点结存）')
        if raw.get('is_manual'):status+=' · 人工修正'
        return {**report_metric(raw,prev,partial if complete else None,partial,status),
                'close_quality':closes.get(day_key,{}).get('quality'),
                'close_source_at':closes.get(day_key,{}).get('source_captured_at'),
                'is_manual':bool(raw.get('is_manual')),
                'manual_operator':raw.get('manual_operator'),
                'manual_updated_at':raw.get('manual_updated_at')}
    today_report=[dict(metric_for(selected_day,g) or {},group_account=g) for g in labels] if selected_day else []
    sel=REPORT_ALL if group=='all' else group
    daily=[]
    for d in dates:
        rec=metric_for(d,sel)
        daily.append(rec if rec is not None else {'business_day':d,'group_account':sel,'status':'未记录','captured_at':None})
    imported={r[0] for r in db.execute(text('SELECT business_day FROM daily_import_days WHERE business_day>=:s AND business_day<=:e'),{'s':start,'e':end}).all()}
    return {'today':today,'selected_day':selected_day,'month':month,'group':group,'groups':labels,'overview':today_report,
            'daily':daily,'available_days':sum(x.get('captured_at') is not None for x in daily),
            'days':len(daily),'imported_days':sorted(imported),
            'warning':'历史余额采用当日最后一次记录，免费服务器休眠时无法保证精确24:00，系统会标注结算来源；缺失日期显示“未记录”。如需严格24点结存，请配置持续在线的任务与持久化数据库。',
            'tracking_started':db.execute(text("SELECT value FROM reporting_meta WHERE name='tracking_since'")).scalar()}


@app.get('/api/reports')
def reports(req:Request,month:str|None=None,group:str='all',day:str|None=None):
    require(req)
    with engine.begin() as db:
        result=build_report(db,month,group,day)
    return JSONResponse(result,headers={'Cache-Control':'no-store, max-age=0'})


@app.get('/api/reports/export.xlsx')
def report_export(req:Request,month:str|None=None,group:str='all'):
    require(req)
    with engine.begin() as db:
        report=build_report(db,month,group)
    wb=Workbook()
    ws=wb.active;ws.title='分组本月逐日' if group!='all' else '全盘本月逐日'
    headers=['日期','新增人数','今日投注（人数）','投注对比','今日充值','今日提现','手续费10%','团队输赢','泡沫','余额','平均余额','本月累计收益','采集情况','最后采集时间']
    ws.append([f"万诚数据统计（{month or current_day()[:7]}） · "+('全盘' if group=='all' else group+'组')]);ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=len(headers))
    ws.append(headers)
    fields=('business_day','new_count','member_count','count_change','new_stake_cents','withdraw_cents',
            'fee_cents','profit_cents','betting_cents','balance_cents','avg_balance_cents','monthly_profit_cents','status','captured_at')
    for r in report['daily']:
        ws.append([round(r.get(k,0)/100) if k.endswith('_cents') and r.get(k) is not None else (r.get(k) if r.get(k) is not None else '未记录') for k in fields])
    ws.freeze_panes='B3';ws.auto_filter.ref=f'A2:N{ws.max_row}'
    ws.row_dimensions[1].height=28
    for cell in ws[1]:cell.fill=PatternFill('solid',fgColor='16486A');cell.font=Font(color='FFFFFF',bold=True,size=15)
    for cell in ws[2]:cell.fill=PatternFill('solid',fgColor='DBEFE6');cell.font=Font(color='154B38',bold=True)
    for col in 'ABCDEFGHIJKLMN':ws.column_dimensions[col].width=20 if col not in 'AMN' else 28
    ws.column_dimensions['A'].width=17
    for row in ws.iter_rows(min_row=3):
        for col in (4,8,9,12):
            cell=row[col-1]
            if isinstance(cell.value,(int,float)):
                cell.font=Font(color='11844E' if cell.value>0 else 'BB3947' if cell.value<0 else '232F42')
    foot=ws.max_row+2;ws.cell(foot,1,report['warning']);ws.merge_cells(start_row=foot,start_column=1,end_row=foot,end_column=len(headers))
    target=io.BytesIO();wb.save(target)
    filename=f'Wancheng-{report["month"]}-{group}.xlsx'
    return Response(target.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="{filename}"'})

# V16: corrections are separate from sampled facts and member financial records.
REPORT_EDIT_FIELDS=('member_count','new_count','new_stake_cents','withdraw_cents','balance_cents')

def validate_report_override_request(data):
    day=str(data.get('day',''))
    valid_date(day)
    if day>current_day():raise HTTPException(400,'不允许修正未来日期')
    group=str(data.get('group',''))
    if group not in REPORT_GROUPS:raise HTTPException(400,'只能修正指定小组，全部总计自动汇总')
    expected=data.get('expected_updated_at','')
    if not isinstance(expected,str) or len(expected)>60:raise HTTPException(400,'修正版本无效')
    return day,group,expected

@app.put('/api/admin/reports/override')
def report_override_save(req:Request,data:dict):
    admin=require(req,'admin',True)
    day,group,expected=validate_report_override_request(data)
    if day==current_day():
        raise HTTPException(409,'今日报表必须实时匹配会员原始数据，不能手动修正；历史日期仍可修改')
    payload=data.get('values')
    if not isinstance(payload,dict) or set(payload)!=set(REPORT_EDIT_FIELDS):
        raise HTTPException(400,'请填写全部五项原始统计字段')
    parsed={}
    for field in REPORT_EDIT_FIELDS:
        raw=payload[field]
        if isinstance(raw,bool):raise HTTPException(400,'数据格式无效')
        if field in ('member_count','new_count'):
            v=str(raw).strip()
            if not re.fullmatch(r'\d{1,8}',v):raise HTTPException(400,'人数必须为非负整数')
            parsed[field]=int(v)
        else:
            v=str(raw).strip()
            if not re.fullmatch(r'(?:0|[1-9]\d{0,12})(?:\.\d{1,2})?',v):
                raise HTTPException(400,'金额必须是非负数，最多两位小数')
            parsed[field]=int(Decimal(v)*100)
    if parsed['new_count']>parsed['member_count']:
        raise HTTPException(400,'新增人数不得超过团队人数')
    with engine.begin() as db:
        write_lock(db)
        record=db.execute(text('SELECT updated_at FROM report_manual_overrides WHERE business_day=:d AND group_account=:g'),{'d':day,'g':group}).scalar()
        if (record or '')!=expected:raise HTTPException(409,'其他管理员已修改报表，请刷新后重试')
        original=db.execute(text('SELECT 1 FROM daily_group_snapshots WHERE business_day=:d AND group_account=:g'),{'d':day,'g':group}).first()
        if not original:raise HTTPException(409,'当天没有已采集快照，不能凭空覆盖历史数据')
        stamp=datetime.now(timezone.utc).isoformat(timespec='microseconds')
        args={'d':day,'g':group,'v':json.dumps(parsed,ensure_ascii=False),'o':admin.get('username',''),'t':stamp}
        db.execute(text('''INSERT INTO report_manual_overrides (business_day,group_account,values_json,operator,updated_at)
          VALUES (:d,:g,:v,:o,:t) ON CONFLICT(business_day,group_account) DO UPDATE
          SET values_json=excluded.values_json,operator=excluded.operator,updated_at=excluded.updated_at'''),args)
        audit(db,'report_manual_override',{'business_day':day,'group':group,'values':parsed},args['o'])
    return {'ok':True,'updated_at':stamp}

@app.delete('/api/admin/reports/override')
def report_override_delete(req:Request,data:dict):
    admin=require(req,'admin',True)
    day,group,expected=validate_report_override_request(data)
    with engine.begin() as db:
        write_lock(db)
        current=db.execute(text('SELECT updated_at FROM report_manual_overrides WHERE business_day=:d AND group_account=:g'),{'d':day,'g':group}).scalar()
        if current is None:raise HTTPException(404,'没有可恢复的报表修正')
        if current!=expected:raise HTTPException(409,'其他管理员已修改报表，请刷新后重试')
        db.execute(text('DELETE FROM report_manual_overrides WHERE business_day=:d AND group_account=:g'),{'d':day,'g':group})
        audit(db,'report_override_reset',{'business_day':day,'group':group},admin.get('username',''))
    return {'ok':True}

@app.post('/api/admin/team-name/{member_id}')
def set_team_name(member_id:str,req:Request,data:dict):
    admin=require(req,'admin',True)
    name=str(data.get('name','')).strip()
    if len(name)>20:raise HTTPException(400,'团队名称最多20字')
    with engine.begin() as db:
        write_lock(db)
        rows,_=sums(active_rows(db))
        r=next((x for x in rows if x['id']==member_id),None)
        if not r:raise HTTPException(404,'会员不存在')
        if r['level']!=2:raise HTTPException(400,'仅第2层会员可设置团队名称')
        if name:
            db.execute(text('''INSERT INTO team_names(member_id,name,updated_at) VALUES (:i,:n,:t)
                ON CONFLICT(member_id) DO UPDATE SET name=excluded.name, updated_at=excluded.updated_at'''),
                {'i':member_id,'n':name,'t':utc_now()})
        else:
            db.execute(text('DELETE FROM team_names WHERE member_id=:id'),{'id':member_id})
        audit(db,'team_name',{'member':r['account'],'name':name},admin.get('username',''))
    return {'ok':True,'name':name}


# V34 流星AI学院: only creates independent academy tables and routes.
from academy import register_academy
register_academy(app,engine,require,utc_now)
