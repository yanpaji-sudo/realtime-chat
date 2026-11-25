"""Isolated Berlin historical newcomer UI tests (no production database)."""
from pathlib import Path
import subprocess

app=Path('member-tree/app.py').read_bytes()
js=Path('member-tree/static/app.js').read_text(encoding='utf-8')
html=Path('member-tree/static/index.html').read_text(encoding='utf-8')

assert 'berlinHistoryCalendar' in js
assert 'berlinHistoryDate' in js
assert '历史新增' in js and '前一天' in js and '后一天' in js
assert 'berlinHistorySwitchDate' in js
assert 'berlinHistoryExpandAncestors' in js
assert 'berlinHistoryMatches' in js
assert 'berlin-history-svg-ring' in js
assert "if(view==='tree'){" in js
assert 'berlin-history-new' in html
assert 'withdraw-red-outer' in js and 'withdraw-red-inner' in js
assert 'berlin-history-ring-pulse' in html

node_test=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const start=js.indexOf('let berlinHistorySelectedDay=dateNow();');
const end=js.indexOf('\nfunction renderBranch(){',start);
assert(start>0&&end>start,'history helper injection section should be unique');
const rows=[
 {id:'root',account:'root',joined_on:'2026-11-01',parent_id:null},
 {id:'alice',account:'alice',joined_on:'2026-11-23',parent_id:'root'},
 {id:'bob',account:'bob',joined_on:'2026-11-24',parent_id:'root'},
 {id:'carol',account:'carol',joined_on:'2026-11-24',parent_id:'alice'},
 {id:'hidden',account:'root_missing',joined_on:'2026-11-24',parent_id:null,
  remark:'上级占位（待补资料）'}
];
let focuses=[],renderCalls=0,controlCalls=0,visible=rows;
const sandbox={
 dateNow:()=> '2026-11-25',
 members:rows,
 teamFocusId:null,
 shownTreeMembers:()=>visible,
 teamExportRows:()=>visible,
 view:'branch',
 collapsed:new Set(['root','alice']),
 requestAnimationFrame:(cb)=>cb(),
 render:()=>{renderCalls++},
 mk:()=>{throw new Error('calendar DOM creation should be mocked')},
 el:()=>null,
};
vm.createContext(sandbox);
vm.runInContext(js.slice(start,end),sandbox);
const check=(code)=>vm.runInContext(code,sandbox);
assert.strictEqual(check("berlinHistoryDateShift('2026-11-01',-1)"),'2026-10-31');
assert.strictEqual(check("berlinHistoryDateShift('2026-12-31',1)"),'2027-01-01');
assert.strictEqual(check("berlinHistoryDateShift('2026-02-30',-1)"),null);
assert.strictEqual(check("berlinHistoryDateShift('not-a-date',1)"),null);
assert.strictEqual(check("berlinHistoryMatches('2026-11-24').length"),2);
assert.strictEqual(check("berlinHistoryMatches('2026-11-23')[0].account"),'alice');
assert.strictEqual(check("berlinHistoryMatches('2026-11-25').length"),0);
const closed=new Set(['root','alice']);
sandbox.tmpClosed=closed;
check("berlinHistoryExpandAncestors(['carol'],tmpClosed)");
assert.strictEqual(closed.size,0,'Ancestors of newly joined member must be unfolded');
sandbox.berlinHistoryBranchController={revealAndDraw:(id)=>focuses.push(id)};
sandbox.berlinHistoryEnsureControls=()=>{controlCalls++};
check("berlinHistorySwitchDate('2026-11-24')");
assert.strictEqual(check('berlinHistorySelectedDay'),'2026-11-24');
assert.deepStrictEqual(focuses,['bob'],'Date change should focus first matched account');
assert.strictEqual(controlCalls,1);
assert.strictEqual(renderCalls,0,'Branch selection should not rebuild the entire page');
check("berlinHistorySwitchDate('2026-11-23')");
assert.strictEqual(check('berlinHistorySelectedDay'),'2026-11-23');
assert.strictEqual(focuses[1],'alice');
check("berlinHistorySwitchDate('2026-11-25')");
assert.strictEqual(check('berlinHistorySelectedDay'),'2026-11-25');
assert.strictEqual(focuses[2],null,'Days with no signups must hide ring and not throw');
check("berlinHistorySwitchDate('2026-11-26')");
assert.strictEqual(check('berlinHistorySelectedDay'),'2026-11-25','No future days');
check("berlinHistorySwitchDate('2026-10-20')");
assert.strictEqual(check('berlinHistorySelectedDay'),'2026-11-25','No dates earlier than oldest');
visible=[rows[0],rows[1]];
assert.strictEqual(check("berlinHistoryMatches('2026-11-24').length"),0,
 'Group scoping must exclude members not in the selected tree');
sandbox.view='tree';
check("berlinHistorySwitchDate('2026-11-23')");
assert.strictEqual(renderCalls,1,'Standard member tree gets a redraw');
assert.strictEqual(sandbox.collapsed.size,0,'Tree ancestors must expand for selected join day');
console.log('PASS: historical calendar day stepping, group scope, placeholder excluded, show all daily newcomers, expand paths, center focus, empty days');
"""
subprocess.run(['node','-e',node_test],check=True)
subprocess.run(['node','--check','member-tree/static/app.js'],check=True)
print('PASS: independent historical newcomer cyan rings in SVG and standard tree, withdrawal rings retained, no API changes')
