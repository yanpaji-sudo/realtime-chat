// Regression: V22 compact popup keeps the correct member/name/amount fields,
// now adds a sortable historical withdrawal-count column and a single ring.
require('./test_single_red_ring_sortable_list.cjs');
const fs=require('fs'),assert=require('assert');
const js=fs.readFileSync('member-tree/static/app.js','utf8');
const html=fs.readFileSync('member-tree/static/index.html','utf8');
assert(js.includes('v22-hist-member-name'));
assert(js.includes('v22-hist-member-account'));
assert(js.includes('v22-hist-member-amount'));
assert(js.includes('v22-hist-member-count'));
assert(js.includes('v22HistSortBy(key)'));
assert(!js.includes("class:'v22-hist-count-badge'"));
assert(html.includes('v22-history-compact-soft-css'));
assert(html.includes('v22-one-ring-sortable-history-css'));
console.log('PASS: compact historical name/account/amount/count rows and single ring retain original popup functionality');
