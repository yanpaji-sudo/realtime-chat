"""No-database Berlin six-column import regression test for repeated accounts.

Loads only the source function via AST so no Render credentials or production
PostgreSQL access are required.
"""
import ast
import csv
import io
import os
import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)

def valid_date(v):
    date.fromisoformat(v)

def legacy_account(v):
    return str(v or '').strip()

def parse_formal_legacy_export(payload, filename):
    raise AssertionError('Six-column file fell through to old parser')

source = Path('member-tree/app.py').read_text(encoding='utf-8')
module = ast.parse(source)
matches = [node for node in module.body if isinstance(node, ast.FunctionDef)
           and node.name == 'parse_legacy_full_export']
assert len(matches) == 1, 'Expected one six-column parser'
sandbox = dict(HTTPException=HTTPException,valid_date=valid_date,
               legacy_account=legacy_account,parse_formal_legacy_export=parse_formal_legacy_export,
               re=re,os=os,io=io,csv=csv,date=date,datetime=datetime,
               Decimal=Decimal,ROUND_HALF_UP=ROUND_HALF_UP)
exec(compile(ast.Module(body=matches,type_ignores=[]),'member-tree/app.py','exec'),sandbox)
parser = sandbox['parse_legacy_full_export']
rows = [
 '会员账号,真实姓名,隶属代理商,历史总充值,历史总提现,注册时间',
 'Gxf123456,第一次,ROOT,10,1,2026-10-01',
 'OTHER,正常账号,ROOT,30,2,2026-10-03',
 'gxf123456,最后一次,ROOT,55.5,4,2026-10-05',
]
result = parser(('\n'.join(rows)+'\n').encode('utf-8'),'members.csv')
target = [x for x in result if x['account'].casefold()=='gxf123456']
assert len(target)==1, target
assert target[0]['remark']=='最后一次', target
assert target[0]['stake_cents']==5550, target
assert target[0]['joined_on']=='2026-10-05', target
assert len(result)==3, result  # two real members and one missing parent placeholder
assert result[0]['__duplicate_count__']==1, result
assert '第4行' in result[0]['__duplicate_examples__'][0], result
assert not any('账号重复' in str(x) for x in result)
print('PASS: same-account case-insensitive dedupe; last row wins; preview metadata; placeholder preserved')
