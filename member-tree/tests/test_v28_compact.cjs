
const assert=require('node:assert/strict'),fs=require('node:fs');
const js=fs.readFileSync('static/app.js','utf8'),css=fs.readFileSync('static/style.css','utf8'),html=fs.readFileSync('static/index.html','utf8');
assert(html.includes('id="compactTreeBtn"'));
assert(js.includes("el('compactTreeBtn').onclick=toggleCompactTree"));
assert(js.includes("let compactMode=Boolean(savedTabView.compactMode)"));
assert(js.includes("if(compactMode&&view==='tree')"));
assert(js.includes("const gapY=compactMode?64:139,gapX=compactMode?186:368"));
assert(js.includes("attachCompactHover(group,m)"));
for(const k of ['direct_balance_cents','subtree_balance_cents','direct_stake_cents','subtree_stake_cents','direct_total_withdraw_cents','subtree_total_withdraw_cents','direct_daily_withdraw_cents','subtree_daily_withdraw_cents','direct_profit_cents','subtree_profit_cents'])assert(js.includes(k),k);
assert(css.includes('.v28-compact-tooltip'));assert(css.includes('.v28-member-mini'));
console.log('V28 compact tree, dense branch map, hover full team data tests passed');
