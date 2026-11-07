from pathlib import Path
p=Path('member-tree/static/app.js')
s=p.read_text(encoding='utf-8')
old="const months=Math.max(0,membershipMonths(m.joined_on,businessDay||dateNow()));"
new="""const dayParts=String(businessDay||dateNow()).split('-').map(Number);
 const joinParts=String(m.joined_on||'').split('-').map(Number);
 const fullMonths=(dayParts[0]-joinParts[0])*12+(dayParts[1]-joinParts[1])-(dayParts[2]<joinParts[2]?1:0);
 const months=Number.isFinite(fullMonths)?Math.max(0,fullMonths):0;"""
assert s.count(old)==1, ('months quota anchor missing',s.count(old))
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
t=Path('member-tree/tests/test_v29_position_alert.cjs')
check=t.read_text(encoding='utf-8')
check=check.replace("assert(js.includes('suggest+=v29Position(x).cents'));","assert(js.includes('suggest+=v29Position(x).cents'));\nassert(js.includes('const fullMonths=(dayParts[0]-joinParts[0])*12'));\nassert(!js.includes('const months=Math.max(0,membershipMonths(m.joined_on'));")
t.write_text(check,encoding='utf-8')
print('V29 full month count supports 7+ months without changing color-card age cap.')
