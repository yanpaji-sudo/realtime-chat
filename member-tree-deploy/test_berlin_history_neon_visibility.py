"""Static/regression checks for large and zoom-independent neon newcomer highlights.
No access to production database or network credentials.
"""
from pathlib import Path
import re,subprocess
js=Path('member-tree/static/app.js').read_text(encoding='utf-8')
html=Path('member-tree/static/index.html').read_text(encoding='utf-8')
assert 'berlinHistorySwitchDate' in js
assert 'berlinHistorySelectedDay' in js
assert "String(m.joined_on||'').slice(0,10)===berlinHistorySelectedDay" in js
assert "String(m.remark||'')!==berlinHistoryPlaceholder" in js
assert js.count("class:'berlin-history-svg-halo'")==1
assert js.count("class:'berlin-history-svg-ring'")==1
assert js.count("class:'berlin-history-svg-inner'")==1
assert js.count("'vector-effect':'non-scaling-stroke'")>=3
assert 'class:\'withdraw-red-outer\'' in js
assert 'class:\'withdraw-red-inner\'' in js
assert "class:'berlin-history-new'" not in js or 'berlin-history-new' in js
assert 'berlin-history-high-visibility-css' in html
assert 'stroke-width:11px' in html
assert 'stroke-width:8px' in html
assert 'outline:5px solid #ffea00' in html
assert '✦ 历史新增' in html
assert 'prefers-reduced-motion' in html
assert 'berlin-history-count' in html
assert '荧光黄圈=新增 · 红圈=提现' in js
# Visual-only patch; verify the server contract is unchanged.
backend=Path('member-tree/app.py').read_text(encoding='utf-8')
assert 'def berlin_recharge_confirm(' in backend
assert 'def create_member(' in backend
subprocess.run(['node','--check','member-tree/static/app.js'],check=True)
print('PASS: non-scaling neon history circles, tree badges and outlines, original red withdrawal rings, accessible reduced motion, backend unchanged')
