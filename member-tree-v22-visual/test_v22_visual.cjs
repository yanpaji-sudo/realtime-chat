// V22 free-server visual-only regression checks.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('member-tree/static/app.js','utf-8');
const html=fs.readFileSync('member-tree/static/index.html','utf-8');
const begin=src.indexOf('function v22RankWithdrawalAreas(');
const end=src.indexOf('\nlet v22VisionMode=',begin);
assert(begin>0&&end>begin,'red-ring ranking function missing');
const sandbox={};vm.runInNewContext(src.slice(begin,end)+'\nthis.rank=v22RankWithdrawalAreas;',sandbox);
const group=[
 {x:50,y:50,amount:1},{x:60,y:70,amount:1},{x:80,y:90,amount:1},{x:60,y:110,amount:1},
 {x:50,y:1050,amount:1},{x:60,y:1080,amount:1},{x:90,y:1120,amount:1},
 {x:50,y:2100,amount:100000000}
];
const areas=sandbox.rank(group,440,350);
assert.strictEqual(areas.length,3,JSON.stringify(areas));
assert.deepStrictEqual(Array.from(areas,x=>Number(x.count)),[4,3,1],'must rank count of red rings, NOT withdrawal sum');
assert.strictEqual(sandbox.rank([],440,350).length,0);
for(const term of [
 'function startTour()','function startDensity()','function showSurvey(index)',
 'v22VisionMode','requestAnimationFrame(step)',
 'if(!pos||!visible(pos))continue','isVirtual&&!visible(p)&&!visible(q)',
 'if(isVirtual&&!paintTimer)','paintTimer=setTimeout','draw();persistTabView();',
 '下一处 →','← 上一处','▶ 自动巡视','🔴 爆红密度'])assert(src.includes(term),term);
assert(html.includes('v22-visual-toolbar'));
assert(src.includes("const TREE_GROUPS=['01','02','03','06','08'];"),'formal five teams preserved');
assert(src.includes('function berlinGroupMemberIds(group)'), 'formal group handling preserved');
assert(!src.includes('member-tree-v22-visual-tour-preview-20261122'));
console.log('PASS: free-server V22 ranking 4>3>1, refreshed virtualization, toolbar and five-team formal configuration');
