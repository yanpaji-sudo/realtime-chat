"""Berlin balance-only upload: account, blank column, balance amount.

Accept pasted TSV, CSV and XLSX rows:
    rjh185185<TAB><TAB>10000.75
    zxr516516<TAB><TAB>10000.75
    139397<TAB><TAB>10000.779
also account<TAB>balance and account<TAB>balance<TAB>empty.
All other modes and the previous import/ledger semantics remain untouched.
"""
# Shared parse_lines is also used by recharge and withdrawal; normalize only
# balance mode before original row-length and cents validation.
needle="""        # Extra empty trailing columns are harmless (common with Excel exports).
        while len(parts) > expected and not parts[-1]:
            parts.pop()
        if not parts or not any(parts): continue"""
assert a.count(needle)==1, "Unexpected Berlin financial parser: normalization anchor absent"
replacement="""        # Extra empty trailing columns are harmless (common with Excel exports).
        while len(parts) > expected and not parts[-1]:
            parts.pop()
        if not parts or not any(parts): continue
        # A platform "Upload format for balance" export has account in A,
        # an intentionally blank B column, and balance in C. Preserve these
        # empty slots rather than interpreting C as an extra unexpected value.
        if mode == 'balance' and len(parts) == 3 and parts[1] == '' and parts[2] != '':
            parts=[parts[0],parts[2]]
        if mode == 'balance' and len(parts)==1 and parts[0].strip().lower()=='upload format for balance':
            continue"""
a=a.replace(needle,replacement,1)

# Openpyxl originally reads only A and B for balance mode, discarding C.
# Read A/B/C and apply the same "empty B" normalization.
needle="width = 3 if mode == 'both' else 2"
assert a.count(needle)==1, "Balance preview Excel width anchor changed"
a=a.replace(needle,"width = 3 if mode in ('both','balance') else 2",1)
# When 2nd balance column contains value, old behavior must continue.
# For 3rd position, original parse_lines strips trailing blanks.
# For a CSV/TSV row with a header, skip it without counting an error.
needle="        known = {r['account'] for r in current}\n        matches = sorted(known & set(parsed))\n        unknown = sorted(set(parsed) - known)"
assert a.count(needle)==1, "Balance preview account match anchor changed"
replacement="""        if mode=='balance':
            by_casefold={r['account'].casefold():r['account'] for r in current}
            canonical={}
            for raw,amounts in parsed.items():
                target=by_casefold.get(raw.casefold(),raw)
                if target in canonical:
                    duplicate.append(target)
                canonical[target]=amounts
            parsed=canonical
        known = {r['account'] for r in current}
        matches = sorted(known & set(parsed))
        unknown = sorted(set(parsed) - known)"""
a=a.replace(needle,replacement,1)

# User-facing hint within the existing import interface; do not change the
# balance snapshot logic: users are warned that omitted accounts become zero.
needle="wrap.querySelector('#sample').textContent='填入当前账号模板';"
assert j.count(needle)==1,"Expected existing import sample button once"
j=j.replace(needle,"""// Balance paste and Excel supports a blank column between account and amount.
wrap.querySelector('#importText').placeholder=importMode==='balance'?
 '余额格式：账号 ⇥ 空列 ⇥ 金额\\\\nrjh185185\\\\t\\\\t10000.75\\\\nzxr516516\\\\t\\\\t10000.75\\\\n139397\\\\t\\\\t10000.779':
 wrap.querySelector('#importText').placeholder;
"""+needle,1)
assert "mode in ('both','balance')" in a
assert "len(parts) == 3 and parts[1] == ''" in a
ap.write_text(a,encoding='utf-8')
jp.write_text(j,encoding='utf-8')
