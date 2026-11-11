"""DFX restore only: reconcile non-financial historical fission snapshots safely.
Do NOT change/relax member money, withdrawals, credits, hierarchy, audits, etc.
Deployment is deliberately separated from this build to avoid erasing ephemeral SQLite.
"""
from pathlib import Path
p=Path("member-tree/app.py")
s=p.read_text(encoding="utf-8")

def replace_once(old,new,tag):
 global s
 count=s.count(old)
 assert count==1,(tag,count)
 s=s.replace(old,new,1)

replace_once(
 "        ('daily_fission', ('member_id', 'business_day'), ('ratio_bp',)),\n",
 "",
 "remove fission from monetary conflict list"
)
original="""        state[name] = kept

    # Only discard truly identical duplicated audit/undo rows."""
new="""        state[name] = kept

    # Historical daily-fission ratios are COMPUTED metrics, not stored money.
    # Duplicate member identities can have different same-day ratios before
    # consolidation. Preserve the most recently captured ratio deterministically,
    # and leave member money, withdrawal ledger/credit and ancestry checks strict.
    # The original encrypted user backup remains the authoritative archive.
    snapshot_seen, snapshot_kept = {}, []
    fission_collisions = 0
    for item in state.get('daily_fission', []):
        if not isinstance(item, dict):
            snapshot_kept.append(item)
            continue
        old_id = str(item.get('member_id', ''))
        canonical_id = canonical(old_id)
        item['member_id'] = canonical_id
        key = (canonical_id, str(item.get('business_day', '')))
        if key not in snapshot_seen:
            snapshot_seen[key] = (item, old_id)
            snapshot_kept.append(item)
            continue
        prior, prior_origin = snapshot_seen[key]
        if prior.get('ratio_bp') != item.get('ratio_bp'):
            fission_collisions += 1
        # ISO-8601 timestamps sort lexicographically when both have the same
        # normalized format. If exact times tie, prefer the canonical member
        # rather than a removed alias. Any arbitrary tie is stable.
        time_new = str(item.get('captured_at') or '')
        time_old = str(prior.get('captured_at') or '')
        use_new = (time_new, old_id == canonical_id, old_id) > (
            time_old, prior_origin == canonical_id, prior_origin)
        if use_new:
            prior.update(item)
            snapshot_seen[key] = (prior, old_id)
    state['daily_fission'] = snapshot_kept
    state['_fission_conflicts_reconciled'] = fission_collisions

    # Only discard truly identical duplicated audit/undo rows."""
replace_once(original,new,"insert fission-only merge")
replace_once(
"        audit(db,'restore',{'members':len(rows),'logs':len(logs),'backup_origin':state.get('source','unknown')},actor)",
"        audit(db,'restore',{'members':len(rows),'logs':len(logs),'backup_origin':state.get('source','unknown'),'fission_conflicts_reconciled':state.get('_fission_conflicts_reconciled',0)},actor)",
"restore log"
)
replace_once(
"    return {'ok':True,'members':len(rows),'logs':len(logs),'duplicate_members_removed':duplicate_members_removed}",
"    return {'ok':True,'members':len(rows),'logs':len(logs),'duplicate_members_removed':duplicate_members_removed,'fission_conflicts_reconciled':state.get('_fission_conflicts_reconciled',0)}",
"return summary"
)
assert "重复会员关联的' + name + '记录金额或内容冲突" in s, "financial conflict protection must remain"
assert "('withdrawals', ('member_id', 'business_day'), ('amount_cents',))" in s
assert "('withdraw_credit', ('member_id', 'business_day'), ('credited_cents',))" in s
p.write_text(s,encoding="utf-8")
print("DFX safe restore patch installed; financial fields still protected")
