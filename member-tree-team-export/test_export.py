"""Read-only structural and Excel formatting tests for formal team export."""
import io
from openpyxl import load_workbook
from starlette.requests import Request
import app

def member(mid,account,joined,stake,withdraw,balance,parent=None,profit=None):
    return {
      'id':mid,'account':account,'joined_on':joined,'parent_id':parent,
      'parent_account':None if not parent else '001ROOT',
      'remark':'测试成员','stake_cents':stake,'balance_cents':balance,
      'total_withdraw_cents':withdraw,'daily_withdraw_cents':100,
      'profit_cents':stake-withdraw if profit is None else profit,
      'direct_count':int(mid=='root'), 'descendant_count':2 if mid=='root' else 0
    }

def test_worksheet_order_colors_and_team_scope(monkeypatch):
    root=member('root','001ROOT','2026-07-20',1000000,200000,3000000)
    child=member('child','002CHILD','2026-06-19',500000,600000,200000,'root')
    unrelated=member('other','999OTHER','2026-01-01',80000000,0,80000000)
    all_rows=[root,child,unrelated]
    # The route must not mutate the database: fake DB connection only.
    class DB:
        def __enter__(self):return self
        def __exit__(self,*exc):pass
    class Engine:
        def connect(self):return DB()
    monkeypatch.setattr(app,'engine',Engine())
    monkeypatch.setattr(app,'require',lambda req,*args,**kw: 'admin')
    monkeypatch.setattr(app,'active_rows',lambda db: [])
    monkeypatch.setattr(app,'sums',lambda rows: (all_rows,{}))
    result=app.export_team_styled(Request({'type':'http'}),'001ROOT')
    book=load_workbook(io.BytesIO(result.body),data_only=True)
    assert book.sheetnames==['团队汇总','成员明细','层级汇总']
    summary,detail,levels=[book[n] for n in book.sheetnames]
    assert summary['B5'].value=='001ROOT'
    assert summary['D5'].value==2
    assert summary['D6'].value==15000
    assert summary['F6'].value==8000
    assert detail['C5'].value=='002CHILD'
    assert detail['C6'].value=='001ROOT'
    assert detail['C7'].value is None
    # First tab now immediately shows *all* own-team members beneath the summary.
    assert summary['A12'].value.startswith('团队成员明细')
    assert [summary['A14'].value, summary['A15'].value]==['002CHILD','001ROOT']
    assert [summary['B14'].value, summary['B15'].value]==['2026-06-19','2026-07-20']
    assert summary['C14'].value==5000
    assert summary['D14'].value==6000
    assert summary['E14'].value==2000
    assert summary['F14'].value==-1000
    assert summary['F15'].value==8000
    assert summary['A16'].value is None
    assert summary['C14'].font.color.rgb[-6:]=='087C46'
    assert summary['D14'].font.color.rgb[-6:]=='C62828'
    assert summary['F14'].font.color.rgb[-6:]=='C62828'
    # No numeric cells are right aligned anymore: summary, members and levels.
    for sheet, locations in [
        (summary,['D5','F5','D6','B7','D7','F7','C14','D14','E14','F14']),
        (detail,['A5','F5','G5','H5','J5','K5','M5']),
        (levels,['B5','C5','D5','E5','G5','H5'])
    ]:
        for addr in locations:
            assert sheet[addr].alignment.horizontal=='center',(sheet.title,addr)
    assert detail['G5'].font.color.rgb[-6:]=='087C46'
    assert detail['H5'].font.color.rgb[-6:]=='C62828'
    assert detail['K5'].font.color.rgb[-6:]=='C62828'
    assert detail['K6'].font.color.rgb[-6:]=='087C46'
    assert len(levels['A'])>=6
    assert result.media_type=='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

def test_source_contains_only_read_only_routes():
    from pathlib import Path
    source=Path('app.py').read_text(encoding='utf-8')
    excerpt=source[source.index("@app.get('/api/export/team.xlsx')"):source.index("@app.get('/api/export.xlsx')")]
    assert "require(req, 'admin')" in excerpt
    assert "with engine.connect()" in excerpt
    assert "filter_export_rows" in excerpt
    assert "team.sort" in excerpt
    assert '.execute(' not in excerpt
    js=Path('static/app.js').read_text(encoding='utf-8')
    assert "function teamOnlyShow(id)" in js
    assert "function teamOnlyClear()" in js
    assert "function teamPictureDownload" in js
    assert "function teamExcelDownload" in js
    assert "const shownRows=teamFocusId?teamExportRows(teamFocusId):shownTreeMembers();" in js
    assert "const header=mk('div','v42-team-head')" in js
    assert "teamFocusId=null" in js
    css=Path('static/style.css').read_text(encoding='utf-8')
    assert '.v28-compact-tooltip{pointer-events:auto!important}' in css
