"""Berlin +member form: case-insensitive account/parent identity matching.

Preserve existing member IDs, original account spelling and financial ledger.
"""
from pathlib import Path
old_parent="db.execute(text('SELECT id FROM members WHERE account=:a AND deleted=0'), {'a': account}).mappings().first()"
new_parent="db.execute(text('SELECT id FROM members WHERE lower(account)=lower(:a) AND deleted=0'), {'a': account}).mappings().first()"
assert a.count(old_parent)==1, 'resolved_parent SQL has changed'
a=a.replace(old_parent,new_parent,1)

old_existing="mode='updated'\n            mid=prior['id']"
assert a.count(old_existing)==1,'single create/overwrite patch changed'
a=a.replace(old_existing,"mode='updated'\n            mid=prior['id']\n            account=prior['account']",1)

old_edit="if not old: raise HTTPException(404, '会员不存在')"
assert a.count(old_edit)==1, 'expected editor not found'
a=a.replace(old_edit,old_edit+"\n        if str(old['account']).lower()==account.lower():account=old['account']",1)

needle="function smartPasteApply(){"
assert j.count(needle)==1
canonical="""function berlinMatchMemberAccount(value){
 const raw=String(value||'').trim();
 return members.find(m=>String(m.account||'').toLowerCase()===raw.toLowerCase())||null;
}
"""
j=j.replace(needle,canonical+needle,1)
old="if(r.account)el('editAccount').value=r.account;\n if(r.parent_account)el('editParentAccount').value=r.parent_account;"
new="""const detectedExisting=r.account?berlinMatchMemberAccount(r.account):null;
 const detectedParent=r.parent_account?berlinMatchMemberAccount(r.parent_account):null;
 if(r.account)el('editAccount').value=detectedExisting?.account||r.account;
 if(r.parent_account)el('editParentAccount').value=detectedParent?.account||r.parent_account;"""
assert j.count(old)==1,'smart paste fill has changed'
j=j.replace(old,new,1)
old="if(r.stake)el('editStake').value=r.stake;else el('editStake').value='10000';"
new="""if(r.stake)el('editStake').value=r.stake;
 else el('editStake').value=detectedExisting?String(Number(detectedExisting.stake_cents||0)/100):'10000';
 if(detectedExisting)el('editWithdraw').value=(Number(detectedExisting.total_withdraw_cents||0)/100).toFixed(2);"""
assert j.count(old)==1,'smart paste stake default has changed'
j=j.replace(old,new,1)
old="const target=members.find(x=>x.account.toLowerCase()===input.value.trim().toLowerCase());\n    if(!target)return;"
new="const target=berlinMatchMemberAccount(input.value);\n    if(!target)return;\n    input.value=target.account;"
assert j.count(old)==1,'account autofill lookup has changed'
j=j.replace(old,new,1)
old="const existing=members.find(m=>m.account.toLowerCase()===account.toLowerCase());"
assert j.count(old)==1
j=j.replace(old,"const existing=berlinMatchMemberAccount(account);",1)
# Show canonical form values in the recognition preview.
old="r.account||'未识别'"
assert j.count(old)>=1
j=j.replace(old,"el('editAccount').value||'未识别'",1)
old="r.parent_account||'未识别'"
assert j.count(old)>=1
j=j.replace(old,"el('editParentAccount').value||'未识别'",1)
assert "lower(account)=lower(:a)" in a
assert "function berlinMatchMemberAccount(value)" in j
ap.write_text(a,encoding='utf-8')
jp.write_text(j,encoding='utf-8')
