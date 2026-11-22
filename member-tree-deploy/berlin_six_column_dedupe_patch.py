"""Berlin six-column complete-list upload: deduplicate repeated account rows, latest wins.

Intentionally does not change the normal balance/withdrawal import, the full-roster
replacement transaction, database schema, or any other site.
"""

# `a` and `j` are already-patched app.py and app.js source strings in the Berlin build.
old = "    output=[];seen=set()"
new = "    output=[];seen=set();duplicate_count=0;duplicate_examples=[]"
assert a.count(old) == 1, f"six-column parser declaration mismatch: {a.count(old)}"
a = a.replace(old, new, 1)

old = "            if key in seen:raise ValueError('账号重复')\n            if key==parent.casefold():raise ValueError('上级不能是本人')\n            seen.add(key)"
new = """            if key in seen:
                duplicate_count+=1
                if len(duplicate_examples)<8:
                    duplicate_examples.append(f'{account}（第{num}行）')
            if key==parent.casefold():raise ValueError('上级不能是本人')
            seen.add(key)"""
assert a.count(old) == 1, f"duplicate validator mismatch: {a.count(old)}"
a = a.replace(old, new, 1)

old = "    if not output:raise HTTPException(400,'没有会员记录')"
new = """    # File duplicates are overwritten in source order. A later row takes
    # precedence over an earlier row for all six fields and parent relation.
    # Do not add duplicate rows to the database or create extra nodes.
    latest={}
    for item in output:
        case_key=item['account'].casefold()
        if case_key in latest:del latest[case_key]
        latest[case_key]=item
    output=list(latest.values())
    if output:
        output[0]['__duplicate_count__']=duplicate_count
        output[0]['__duplicate_examples__']=duplicate_examples
    if not output:raise HTTPException(400,'没有会员记录')"""
assert a.count(old) == 1, f"six-column output location mismatch: {a.count(old)}"
a = a.replace(old, new, 1)

old = "'job_id':jobid,'members':len(parsed),'existing_members':len(existing),"
new = """'job_id':jobid,'members':len(parsed),'existing_members':len(existing),
            'duplicates':parsed[0].get('__duplicate_count__',0) if parsed else 0,
            'duplicate_examples':parsed[0].get('__duplicate_examples__',[]) if parsed else [],"""
assert a.count(old) == 1, f"preview result mismatch: {a.count(old)}"
a = a.replace(old, new, 1)

# Show what will happen before the administrator clicks Confirm. Never
# silently merge divergent account amounts/parent relationships.
old = '根节点：${d.roots}个'
new = "文件内重复账号：${d.duplicates||0}条（最后一条记录生效）\\n重复账号示例：${(d.duplicate_examples||[]).join('、')||'无'}\\n根节点：${d.roots}个"
assert j.count(old) == 1, f"preview frontend mismatch: {j.count(old)}"
j = j.replace(old, new, 1)

assert "if key in seen:raise ValueError('账号重复')" not in a
assert 'output=list(latest.values())' in a
assert 'duplicate_examples' in a and 'duplicate_examples' in j
assert '确认覆盖旧会员数据' in a
assert 'UPDATE members SET deleted=1' in a
ap.write_text(a,encoding='utf-8')
jp.write_text(j,encoding='utf-8')
