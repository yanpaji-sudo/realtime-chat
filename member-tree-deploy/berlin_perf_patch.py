"""Performance fix for the independent Berlin tree test; no database migration."""
# Read-only tree/report API requests no longer write daily report snapshots
# on every poll or every administrator session.
old_capture = """def capture_current_report(db,day=None):
    day=day or current_day()
    store_live_report_snapshots(db,report_rows_today(db,day))"""
assert a.count(old_capture)==1, "Unexpected report capture source"
new_capture = """_berlin_sample_lock = threading.Lock()
_berlin_last_sample = {}

def _berlin_sample_due(day):
    # Preserve once-per-day reset; take one snapshot at most every 60 seconds.
    now = monotonic()
    with _berlin_sample_lock:
        last = _berlin_last_sample.get(day)
        if last is not None and now-last < 60:
            return False
        _berlin_last_sample.clear()
        _berlin_last_sample[day] = now
        return True

def capture_current_report(db,day=None):
    day=day or current_day()
    if _berlin_sample_due(day):
        store_live_report_snapshots(db,report_rows_today(db,day))"""
a = a.replace(old_capture,new_capture,1)
old_report = "    store_live_report_snapshots(db,current)"
assert a.count(old_report)==1, "Unexpected report snapshot source"
a = a.replace(old_report,
    "    if _berlin_sample_due(today):\n        store_live_report_snapshots(db,current)",1)

# Use bulk executemany for the periodic fission-history refresh rather than
# one Python/SQLAlchemy execute() call for each member node.
old_fission = """    if update:
        for mid,bp in ratio.items():
            db.execute(text('''INSERT INTO daily_member_fission (member_id,business_day,ratio_bp,captured_at) VALUES (:i,:d,:r,:t)
                  ON CONFLICT(member_id,business_day) DO UPDATE SET ratio_bp=excluded.ratio_bp,captured_at=excluded.captured_at'''),
                  {'i':mid,'d':day,'r':bp,'t':now.isoformat()})"""
assert a.count(old_fission)==1, "Unexpected daily-fission source"
new_fission = """    if update and ratio:
        db.execute(text('''INSERT INTO daily_member_fission (member_id,business_day,ratio_bp,captured_at)
                  VALUES (:i,:d,:r,:t)
                  ON CONFLICT(member_id,business_day) DO UPDATE SET
                    ratio_bp=excluded.ratio_bp,captured_at=excluded.captured_at'''),
            [{'i':mid,'d':day,'r':bp,'t':now.isoformat()} for mid,bp in ratio.items()])"""
a=a.replace(old_fission,new_fission,1)

# Improve SQLite test-server lock waiting without switching journal mode on
# the live DB. The production database is managed PostgreSQL.
old_engine="engine = create_engine(DB_URL, pool_pre_ping=True, connect_args={'check_same_thread': False} if DB_URL.startswith('sqlite:') else {})"
assert a.count(old_engine)==1, "Unexpected SQLAlchemy engine source"
a=a.replace(old_engine,
    "engine = create_engine(DB_URL, pool_pre_ping=True, connect_args={'check_same_thread': False, 'timeout': 15} if DB_URL.startswith('sqlite:') else {})",1)

# Client: one refresh in flight, 45 second polling only in visible tabs.
old_refresh="async function refresh(silent=false){if(!role)return;try{"
assert j.count(old_refresh)==1, "Unexpected client refresh source"
j=j.replace(old_refresh,
    "let berlinRefreshBusy=false;\nasync function refresh(silent=false){if(!role||berlinRefreshBusy)return;berlinRefreshBusy=true;try{",1)
old_end="if(!silent)message('加载失败：'+e.message)}}"
assert j.count(old_end)==1, "Unexpected client refresh error handler"
j=j.replace(old_end,
    "if(!silent)message('加载失败：'+e.message)}finally{berlinRefreshBusy=false}}",1)
old_poll="if(role&&view!=='import'&&!document.querySelector('dialog[open]'))refresh(true)},10000);"
assert j.count(old_poll)==1, "Unexpected client polling source"
j=j.replace(old_poll,
    "if(role&&!document.hidden&&view!=='import'&&!document.querySelector('dialog[open]'))refresh(true)},45000);",1)

# Initial 1,600+ member trees show roots. Users can expand subtrees as needed.
old_members="members=d.members;total=d.totals;businessDay=d.business_day||dateNow();"
assert j.count(old_members)==1, "Unexpected client member-state source"
j=j.replace(old_members,
    "members=d.members;total=d.totals;businessDay=d.business_day||dateNow();if(members.length>1600&&!window.berlinTreeInitialCollapse){collapsed=new Set(members.filter(m=>!m.parent_id).map(m=>m.id));window.berlinTreeInitialCollapse=true;}",1)
old_expand="el('expandAll').onclick=()=>{collapsed.clear();render()};"
assert j.count(old_expand)==1, "Unexpected expand-all button"
j=j.replace(old_expand,
    "el('expandAll').onclick=()=>{if(members.length>2500&&!confirm('当前会员数量较多，展开全部节点可能导致浏览器卡顿。确定继续吗？'))return;collapsed.clear();render()};",1)

assert "berlinRefreshBusy" in j and "_berlin_sample_due(today)" in a
# The builder owns these files; only the isolated Berlin release is changed.
ap.write_text(a)
jp.write_text(j)
