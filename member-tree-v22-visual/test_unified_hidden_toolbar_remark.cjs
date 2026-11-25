// Read-only V22 toolbar and remark-search regression.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const style=fs.readFileSync('member-tree/static/style.css','utf8');
const start=js.indexOf('// V22 unified toolbar, fullscreen Alt+Q toggle');
const end=js.indexOf('function locateBranchAccount(){',start);
assert(start>0&&end>start,'Search helper index invalid: start='+start+', end='+end+', firstLocate='+js.indexOf('function locateBranchAccount(){')+', total='+js.length);
const members=[
 {id:1,account:'000123',remark:'李强 北京'},
 {id:2,account:'a567',remark:'王芳'},
 {id:3,account:'b888',remark:'王芳'},
 {id:4,account:'test012',remark:'北京三组'},
 {id:5,account:'000789',remark:'刘总'},
 {id:6,account:'RAW',remark:''}
];
const frozen=JSON.stringify(members);
const env={members,view:'branch',query:'',document:{},el:()=>null};
vm.createContext(env);
vm.runInContext(js.slice(start,end),env);
const call=x=>vm.runInContext(x,env);
const names=a=>Array.from(a).map(x=>x.account);
assert.strictEqual(call("v22RemarkSearchMatches(members[0],'000')"),true);
assert.strictEqual(call("v22RemarkSearchMatches(members[0],'北京')"),true);
assert.strictEqual(call("v22RemarkSearchMatches(members[1],'北京')"),false);
assert.deepStrictEqual(names(call("v22RemarkSearchCandidates('王芳')")),['a567','b888']);
assert.deepStrictEqual(names(call("v22RemarkSearchLocateMatches('王芳')")),['a567','b888'],
 'Duplicate remark MUST NOT automatically locate one member');
assert.deepStrictEqual(names(call("v22RemarkSearchLocateMatches('000123')")),['000123']);
assert.deepStrictEqual(names(call("v22RemarkSearchLocateMatches('A567')")),['a567'],
 'Fully typed case variant resolves unambiguously');
assert.deepStrictEqual(names(call("v22RemarkSearchLocateMatches('北京')")),['000123','test012']);
assert.deepStrictEqual(names(call("v22RemarkSearchLocateMatches('000')")),[],
 'Partial account may be suggested but never silently precisely located');
assert.deepStrictEqual(names(call("v22RemarkSearchCandidates('000')")),['000123','000789']);
assert.deepStrictEqual(names(call("v22RemarkSearchLocateMatches('不存在')")),[]);
assert.strictEqual(JSON.stringify(members),frozen,'No lookup changes records');
assert(js.includes("v22UnifiedToolbarSetup();selectedLogin('viewer')"));
assert(js.includes("b.append(label,newer,withdraw,week,month,dormant,loan,prev,pick"));
assert(js.includes("document.getElementById('v22UnifiedTrack')"));
assert(js.includes("input.value=String(member.account||'')"));
assert(js.includes("if(candidates.length>1)"),'No accidental double-match autofocus');
assert(js.includes("e.altKey&&String(e.key).toLocaleLowerCase()==='q'"));
assert(js.includes("v22UnifiedToolbarSync();"),'Fallback fullscreen state sync');
assert((js.match(/v22RemarkSearchMatches\(x,query\)/g)||[]).length===5,
 'Account and remark filters reach tree/list/table/ranking/highlights');
assert(style.includes('.panel:fullscreen .v22-unified-dock:not(.v22-unified-open)'));
assert(style.includes('.panel.fullscreen-fallback .v22-unified-dock:not(.v22-unified-open)'));
assert(style.includes('.v22-unified-track .v22-hist-toolbar:not([hidden])'));
assert(style.includes('.panel:has(#v22UnifiedToolbar)>.panel-header{display:none!important}'));
console.log('PASS: V22 linked partial note/strict account search, duplicate candidate safety, 5 view filters, Alt+Q fullscreen hidden toolbar, financial source untouched');
