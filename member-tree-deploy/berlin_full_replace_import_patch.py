"""Restore full-roster replacement for Berlin six-column uploads.

Every confirmed upload defines the current visible member tree. Accounts absent
from the uploaded sheet become inactive (soft-deleted), historical ledgers and
stable member IDs are retained. The existing endpoint wraps this in a database
transaction and checks that no other admin changed the roster since preview.
"""
import re

assert isinstance(branch, str) and "UPDATE members SET deleted=1" in branch
assert "if parsed and parsed[0].get('__berlin__')" in branch
pattern = r"(?ms)^        if parsed and parsed\[0\]\.get\('__berlin__'\):.*?(?=^        now=utc_now\(\);today=current_day\(\))"
matches = list(re.finditer(pattern, a))
assert len(matches) == 1, f"expected one incremental confirmation branch, got {len(matches)}"
assert "berlin_incremental_6_columns" in matches[0].group(0)

# Restore the previously validated replace path, guarding existing real parent
# profiles against being zeroed by automatically generated placeholder parents.
base = branch
old = "                v={'i':mid,'a':row['account'],'j':row['joined_on'],'s':row['stake_cents'],"
new = """                if row.get('__placeholder__') and mid in existing_ids:
                    db.execute(text('''UPDATE members SET deleted=0,parent_id=NULL,
                        revision=revision+1,updated_at=:now WHERE id=:id'''),
                        {'now':now,'id':mid})
                    continue
                v={'i':mid,'a':row['account'],'j':row['joined_on'],'s':row['stake_cents'],"""
assert base.count(old) == 1
base = base.replace(old, new, 1)
old = "            now=utc_now()"
new = """            removed_count=len({str(x['account']).casefold() for x in existing} -
                              {str(x['account']).casefold() for x in parsed})
            now=utc_now()"""
assert base.count(old) == 1
base = base.replace(old, new, 1)
old = "            return {'ok':True,'members':len(parsed),\n                    'placeholders':sum(bool(x.get('__placeholder__')) for x in parsed)}"
new = """            return {'ok':True,'members':len(parsed),'removed':removed_count,
                    'mode':'replace','placeholders':sum(bool(x.get('__placeholder__')) for x in parsed)}"""
assert base.count(old) == 1
base = base.replace(old, new, 1)
a = a[:matches[0].start()] + base + a[matches[0].end():]

old = "'mode':'append' if parsed and parsed[0].get('__berlin__') else 'replace',"
assert a.count(old) == 1
a = a.replace(old, "'mode':'replace',", 1)
old = "'柏林六列追加：只新增或更新本次文件的会员，其他小组不删除、不隐藏；已有上级资料不被占位数据清零。'"
assert a.count(old) == 1
a = a.replace(old,
  "'柏林六列全量覆盖：本次文件决定全部可见会员；不在文件中的旧会员将从当前树状图移除。原有流水保留，已有上级资料不被占位数据清零。'",1)

old = "if payload.get('confirm') not in ('确认覆盖旧会员数据','确认追加会员数据'):"
assert a.count(old) == 1
a = a.replace(old, "if payload.get('confirm')!='确认覆盖旧会员数据':", 1)
old = """        if parsed and parsed[0].get('__berlin__') and payload.get('confirm')!='确认追加会员数据':
            raise HTTPException(400,'六列数据请确认追加会员数据')
"""
assert a.count(old) == 1
a = a.replace(old, "", 1)
assert "确认追加会员数据" not in a
assert "berlin_incremental_6_columns" not in a
assert "UPDATE members SET deleted=1" in a
assert "'mode':'replace'" in a
ap.write_text(a,encoding='utf-8')

old = "将追加／更新本次文件中的会员；其他小组和每日提现、余额记录保持不变。确认继续？"
new = "本次上传将覆盖全部柏林会员名单，未出现在文件中的账号将从当前树状图移除；已有会员的历史流水保留。确认继续？"
assert j.count(old) == 1
j = j.replace(old,new,1)
j = j.replace('确认追加会员数据','确认覆盖旧会员数据')
j = j.replace('（不会删除）','（将按本次文件全量覆盖）')
j = j.replace('预计新增：${d.added_members||0}人（含缺失上级占位）',
              '本次名单：${d.members||0}人（含缺失上级占位）')
old = "result.textContent=`本批处理完成：新增 ${res.added||0} 人，更新 ${res.updated||0} 人；现有会员总计 ${res.total_members||0} 人。`;"
new = "result.textContent=`全量覆盖成功：当前 ${res.members} 位会员，已从树状图移除 ${res.removed||0} 位旧会员。`;"
if old in j:
    j = j.replace(old,new,1)
# Older UI builds use the direct success message instead of the append summary.
j = j.replace("result.textContent='已成功重建会员树 '+res.members+' 位会员及上下级关系。';",
              "result.textContent='已全量覆盖会员树 '+res.members+' 位会员及上下级关系。';")
old = "showToast('已合并上传：新增 '+(res.added||0)+' 人，更新 '+(res.updated||0)+' 人')"
new = "showToast('已全量覆盖会员树：'+res.members+' 人')"
if old in j:
    j = j.replace(old,new,1)
j = j.replace("showToast('成功恢复 '+res.members+' 位会员')",
              "showToast('已全量覆盖 '+res.members+' 位会员')")
j = j.replace('六列数据会追加／更新会员和上下级关系，不会清空其他组。',
              '六列表格会全量覆盖现有会员树；如需保留其他小组，请将其会员也包含在本次文件中。')
j = j.replace('不同小组可以分批上传，原有其他组不删除。',
              '每次需要上传完整名单；未包含的会员及小组将从当前树状图移除。')
assert '确认追加会员数据' not in j
assert '本批处理完成：新增' not in j
assert '已合并上传' not in j
assert '全量覆盖' in j
jp.write_text(j,encoding='utf-8')
