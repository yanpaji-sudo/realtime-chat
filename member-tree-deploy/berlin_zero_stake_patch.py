"""Berlin: Allow manually entered member initial stake to be zero yuan.

Scope: the Add / Edit Member dialog and shared member validator ONLY.
Do not change defaults, existing balances, withdrawal / recharge ledgers,
membership records, API routes, or deployed database content.
"""
import re
old_guard="if stake <= 0 or stake > 10**16:"
new_guard="if stake < 0 or stake > 10**16:"
assert a.count(old_guard)==1, f"Expected member stake validator once, found {a.count(old_guard)}"
a=a.replace(old_guard,new_guard,1)
# Update the backend's human-readable validation error; 0 is now valid.
old_msg="建仓资金必须是有效的正数"
if old_msg in a:a=a.replace(old_msg,"建仓资金必须为0元或有效的非负金额",1)

html_pattern=re.compile(r'<input\b[^>]*\bid\s*=\s*["\']editStake["\'][^>]*>',re.I|re.S)
matches=list(html_pattern.finditer(h))
assert len(matches)==1, f"Expected exact editStake HTML input, got {len(matches)}"
tag=matches[0].group(0)
old_min=re.search(r'\bmin\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)',tag,re.I)
assert old_min is not None, f"Cannot identify numeric minimum in stake field: {tag!r}"
tag=tag[:old_min.start()]+'min="0"'+tag[old_min.end():]
# 0 must pass the step constraint. Keep decimal precision of 0.01 yuan.
old_step=re.search(r'\bstep\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)',tag,re.I)
if old_step:
    tag=tag[:old_step.start()]+'step="0.01"'+tag[old_step.end():]
else:
    tag=tag[:-1]+' step="0.01">'
h=h[:matches[0].start()]+tag+h[matches[0].end():]
assert 'min="0"' in tag
assert 'step="0.01"' in tag

ap.write_text(a,encoding='utf-8')
hp.write_text(h,encoding='utf-8')
print('PASS: backend >= 0, member amount min=0 step=0.01; default deposit unchanged')
