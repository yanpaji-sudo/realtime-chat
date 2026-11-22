"""Allow + 新增会员 to overwrite existing account's five editable fields.
Only the independent Berlin test source is patched. Keep IDs, existing
balances and daily withdrawal, current account history and other members.
"""
from textwrap import dedent
route_begin=a.index("@app.post('/api/members')\ndef create_member(")
route_end=a.index("\n@app.put('/api/members/{mid}')",route_begin)
old_create=a[route_begin:route_end]
assert "raise HTTPException(409, '会员账号已存在')" in old_create
new_create=r"""@app.post('/api/members')
def create_member(data: MemberIn, req: Request):
    operator=require(req,'admin',True)
    account,withdrawn,stake=validate_member(data)
    mid=str(uuid.uuid4())
    mode='created'
    with engine.begin() as db:
        write_lock(db)
        settle_past_days(db)
        prior=db.execute(text('SELECT * FROM members WHERE lower(account)=lower(:a) LIMIT 1'),
                         {'a':account}).mappings().first()
        parent=resolved_parent(db,data)
        parent_ok(db,parent,prior['id'] if prior else None)
        validate_stake_for_level(db,parent,stake)
        now=utc_now()
        if prior:
            mode='updated'
            mid=prior['id']
            if data.expected_revision is not None and int(prior['revision'])!=data.expected_revision:
                raise HTTPException(409,'该会员资料已更新，请刷新后再次核对再覆盖')
            old={k:prior[k] for k in SNAPSHOT_FIELDS}
            try:
                result=db.execute(text("""UPDATE members SET account=:a,joined_on=:j,parent_id=:p,
                    total_withdraw_cents=:w,stake_cents=:stake,remark=:remark,deleted=0,
                    updated_at=:t,revision=revision+1 WHERE id=:id AND revision=:expected"""),
                    {'a':account,'j':data.joined_on,'p':parent,'w':withdrawn,'stake':stake,
                     'remark':data.remark.strip(),'t':now,'id':mid,'expected':prior['revision']})
                if result.rowcount!=1:
                    raise HTTPException(409,'已有会员刚被其他管理员修改，请刷新后再覆盖')
            except IntegrityError:
                raise HTTPException(409,'该账号与其他会员存在冲突')
            record_undo(db,operator.get('username',''),'update',f'新增入口覆盖会员 {account}',
               [{'id':mid,'account':account,'before':old,'after':snapshot(db,mid)}])
            audit(db,'update',{'mode':'single_account_latest_wins','before':{
                'account':prior['account'],'joined':prior['joined_on'],
                'parent':prior['parent_id'],'stake':prior['stake_cents'],
                'total':prior['total_withdraw_cents'],'remark':prior['remark']},
                'after':{'account':account,'joined':data.joined_on,'parent':parent,
                'stake':stake,'total':withdrawn,'remark':data.remark.strip()}},
                operator.get('username',''))
        else:
            try:
                db.execute(text("""INSERT INTO members(id,account,joined_on,parent_id,
                    total_withdraw_cents,stake_cents,remark,created_at,updated_at)
                    VALUES (:id,:a,:j,:p,:w,:stake,:remark,:t,:t)"""),
                    {'id':mid,'a':account,'j':data.joined_on,'p':parent,'w':withdrawn,
                     'stake':stake,'remark':data.remark.strip(),'t':now})
            except IntegrityError:
                raise HTTPException(409,'此账号刚被其他管理员新增，请重新核对后提交')
            record_undo(db,operator.get('username',''),'create',f'新增会员 {account}',
               [{'id':mid,'account':account,'before':None,'after':snapshot(db,mid)}])
            audit(db,'create',{'account':account,'remark':data.remark.strip()},
                  operator.get('username',''))
        capture_current_report(db)
    return {'ok':True,'id':mid,'mode':mode,
            'message':'已有账号已按最后提交覆盖' if mode=='updated' else '新会员创建成功'}
"""
a=a[:route_begin]+new_create+a[route_end:]
assert a.count("def create_member(")==1
# Update explicit UI warning rather than displaying the old duplicate-creation refusal.
old_warning="warnings.push('本人账号已存在，请核对，系统不会重复创建')"
if old_warning in j:
    j=j.replace(old_warning,"warnings.push('该账号已存在，点击保存会覆盖此账号资料（不会覆盖余额和每日流水）')",1)
else:
    assert "已存在" in j, 'Smart paste member warning not found'
old_title="el('dialogTitle').textContent=m?'编辑会员':'新增会员';"
assert j.count(old_title)==1
j=j.replace(old_title,"el('dialogTitle').textContent=m?'编辑会员':'新增会员 / 覆盖已有账号';",1)
start=j.index('async function saveEdit(e){')
end=j.index('\nasync function removeEdit()',start)
new_save=r"""async function saveEdit(e){
 e.preventDefault();
 const account=el('editAccount').value.trim();
 const existing=members.find(m=>m.account.toLowerCase()===account.toLowerCase());
 if(!editId&&existing){
  const notice='会员账号 '+existing.account+' 已存在。\n确认用当前填写的姓名备注、上级、加入日期、建仓和累计提现覆盖吗？\n余额、当日提现及历史流水不会清空。';
  if(!window.confirm(notice))return;
 }
 const payload={account,joined_on:el('editDate').value,
  parent_account:el('editParentAccount').value.trim()||null,
  stake:el('editStake').value,total_withdraw:el('editWithdraw').value.trim(),
  remark:el('editRemark').value.trim(),
  expected_revision:editId?(members.find(x=>x.id===editId)?.revision??null):
   (existing?existing.revision??null:null)};
 try{
  const response=await api(editId?'/members/'+editId:'/members',editId?'PUT':'POST',payload);
  el('editDialog').close();
  showToast(editId?'会员已更新':response.mode==='updated'?'已覆盖原会员资料（账号不重复）':'会员添加成功');
  await refresh();await syncUndoStatus();
 }catch(e){el('editError').textContent=e.message}
}"""
j=j[:start]+new_save+j[end:]
# Auto-fill an already-existing member after account entry in the single-add form,
# avoiding accidental overwrites of fields hidden in the previous entry.
anchor="el('editDialog').showModal()}"
assert j.count(anchor)==1
j=j.replace(anchor,r"""if(!m){
  const input=el('editAccount');
  input.onchange=()=>{
    if(editId)return;
    const target=members.find(x=>x.account.toLowerCase()===input.value.trim().toLowerCase());
    if(!target)return;
    const byId=index();
    el('editDate').value=target.joined_on||dateNow();
    el('editStake').value=String(Number(target.stake_cents||0)/100);
    el('editWithdraw').value=(Number(target.total_withdraw_cents||0)/100).toFixed(2);
    el('editRemark').value=target.remark||'';
    el('editParentAccount').value=target.parent_id?(byId.get(target.parent_id)?.account||''):'';
    el('editError').textContent='已自动填入现有账号 '+target.account+' 的原资料，修改后保存将覆盖（余额及日流水不变）。';
  };
 }else el('editAccount').onchange=null;
 el('editDialog').showModal()}""",1)
assert j.count('async function saveEdit(')==1
assert "response.mode==='updated'" in j
ap.write_text(a,encoding='utf-8')
jp.write_text(j,encoding='utf-8')
