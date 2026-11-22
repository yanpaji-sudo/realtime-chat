"""Safely auto-select the proper import mode for clearly labeled pasted triplets.
Only affects UI routing; preserves confirm interaction and all ledger logic.
"""
anchor="wrap.querySelector('#previewButton').onclick=async()=>{const fd=new FormData();"
assert j.count(anchor)==1, f"Expected one preview handler, got {j.count(anchor)}"
new_handler=r"""wrap.querySelector('#previewButton').onclick=async()=>{
const typedLines=wrap.querySelector('#importText').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
const first=typedLines[0]||'';
const clearTriplet=typedLines.length>=3 &&
    /^[\u3400-\u9fff]/.test(first) &&
    /^[A-Za-z0-9_.-]{1,64}$/.test(typedLines[1]) &&
    /^[+-]?\d+(?:\.\d+)?$/.test(typedLines[2]);
if(clearTriplet){
 const detected=/充值|存款/.test(first)?'recharge':(/提现/.test(first)?'daily':'');
 if(detected&&detected!==importMode){
  importMode=detected;
  wrap.querySelectorAll('.mode').forEach(b=>b.classList.toggle('selected',b.dataset.mode===importMode));
  showToast(detected==='recharge'?'已自动识别为当日充值流水':'已自动识别为当日提现流水');
 }
}
const fd=new FormData();"""
j=j.replace(anchor,new_handler,1)
old="if(!d.valid)showToast('检查发现问题，本批次不可提交')"
assert j.count(old)==1, f"Missing unmatched-account alert anchor: {j.count(old)}"
new="if(!d.valid)showToast(d.unmatched_count?'未找到会员账号：'+d.unmatched.slice(0,3).join('、'):'检查发现问题，本批次不可提交')"
j=j.replace(old,new,1)
old_placeholder="wrap.querySelector('#importText').placeholder='首次存款\\nF123576\\n3000\\n充值/更换电池\\nhkfu258\\n184.786';"
# Preserve known example but add exact common Chinese recharge synonym.
if old_placeholder in j:
 j=j.replace(old_placeholder, "wrap.querySelector('#importText').placeholder='首次充值\\nF123576\\n3000\\n充值/更换电池\\nhkfu258\\n184.786';",1)
assert "const clearTriplet=typedLines.length>=3" in j
assert "未找到会员账号" in j
jp.write_text(j,encoding='utf-8')
