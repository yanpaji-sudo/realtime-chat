"""Allow account-first OR amount-first two-column imports in Berlin.

Covers balance, recharge and withdrawal previews (pasted text/TSV/CSV/Excel).
Member lookup resolves the direction, including all-digit member accounts.
If both cells refer to existing numeric accounts, reject ambiguity rather than
silently crediting the wrong person. Does not change settlement, balance
accounting, withdrawal sign rules, roster data or full-snapshot behavior.
"""
helper=r'''
def berlin_finance_row_order(lines, mode, member_accounts):
    """Canonicalize two-field finance rows using existing member IDs and amounts.

    For withdrawals: an amount-first POSITIVE amount is an actual withdrawal,
    matching the pre-existing reverse-cashflow format. Account-first two-column
    rows retain their pre-existing signed net convention.
    """
    known={str(acct).casefold():str(acct) for acct in member_accounts}
    account_pattern=r'[A-Za-z0-9_.-]{1,64}'

    def valid_money(v):
        try:
            berlin_import_amount_cents(v)
            return True
        except HTTPException:
            return False

    out=[]
    for line_number,row in enumerate(lines,1):
        if isinstance(row,(tuple,list)):
            vals=[str(x).replace('\ufeff','').strip() if x is not None else '' for x in row]
            while len(vals)>2 and not vals[-1]:vals.pop()
        else:
            raw=str(row).replace('\ufeff','').strip()
            if not raw:
                out.append(row);continue
            # Support original heading and simple table column labels.
            if raw.casefold() in ('upload format for balance','amount account',
                                  'account amount','amount balance','balance account'):
                out.append(row);continue
            if '\t' in raw:
                vals=[v.strip() for v in raw.split('\t')]
            elif re.search(r'\s',raw):
                vals=raw.split()
            elif any(d in raw for d in ('，',';', '；','|')):
                vals=[v.strip() for v in re.split(r'[，;；|]',raw)]
            elif ',' in raw:
                vals=[v.strip() for v in raw.split(',')]
            else:
                out.append(row);continue
            while len(vals)>2 and not vals[-1]:vals.pop()
        # A=account, B=empty, C=balance (or same layout in reverse).
        if len(vals)==3 and vals[1]=='':
            vals=[vals[0],vals[2]]
        if len(vals)!=2 or not all(vals):
            out.append(row);continue
        first,second=vals
        first_acct=bool(re.fullmatch(account_pattern,first))
        second_acct=bool(re.fullmatch(account_pattern,second))
        first_money=valid_money(first)
        second_money=valid_money(second)
        first_known=first_acct and first.casefold() in known
        second_known=second_acct and second.casefold() in known

        reverse=None
        if first_known and second_known and first_money and second_money:
            raise HTTPException(400,f'第{line_number}行两个数字都属于现有会员账号，无法确定哪个是金额，请使用带明确列名的表格')
        if first_known and second_money and not second_known:
            reverse=False
        elif second_known and first_money and not first_known:
            reverse=True
        elif first_acct and second_money and not first_money:
            reverse=False
        elif second_acct and first_money and not second_money:
            reverse=True
        elif first_acct and second_acct and first_money and second_money:
            # Unknown all-numeric account: an integer account with a decimal
            # amount can be inferred, but never guess for two bare integers.
            if '.' in first and '.' not in second and second.isdigit():
                reverse=True
            elif '.' in second and '.' not in first and first.isdigit():
                reverse=False
        if reverse is None:
            out.append(row);continue

        acct,amt=(second,first) if reverse else (first,second)
        acct=known.get(acct.casefold(),acct)
        if mode=='daily' and reverse:
            value=abs(berlin_import_amount_cents(amt))
            amt=f'-{value//100}.{value%100:02d}' if value else '0'
        out.append([acct,amt])
    return out
'''
anchor="@app.post('/api/import/preview')"
assert a.count(anchor)==1,'Financial preview insertion anchor changed'
a=a.replace(anchor,helper+'\n'+anchor,1)

old="""    cashflow_count=cashflow_repeat=0
    if mode=='daily':
        lines,cashflow_count,cashflow_repeat=berlin_three_line_cashflow(lines,'daily')
    parsed, errors, duplicate, padded_daily = parse_lines(lines, mode)"""
new="""    cashflow_count=cashflow_repeat=0
    if mode=='daily':
        lines,cashflow_count,cashflow_repeat=berlin_three_line_cashflow(lines,'daily')
    if mode in ('balance','daily'):
        with engine.connect() as lookup_db:
            accounts=[r[0] for r in lookup_db.execute(
                text('SELECT account FROM members WHERE deleted=0')).all()]
        lines=berlin_finance_row_order(lines,mode,accounts)
    parsed, errors, duplicate, padded_daily = parse_lines(lines, mode)"""
assert a.count(old)==1,'Balance and withdrawal preview parsing anchor changed'
a=a.replace(old,new,1)

old="""    lines,cashflow_count,cashflow_repeat=berlin_three_line_cashflow(lines,'recharge')
    parsed,errors,duplicate,_=parse_lines(lines,'balance')"""
new="""    lines,cashflow_count,cashflow_repeat=berlin_three_line_cashflow(lines,'recharge')
    with engine.connect() as lookup_db:
        accounts=[r[0] for r in lookup_db.execute(
            text('SELECT account FROM members WHERE deleted=0')).all()]
    lines=berlin_finance_row_order(lines,'recharge',accounts)
    parsed,errors,duplicate,_=parse_lines(lines,'balance')"""
assert a.count(old)==1,'Recharge preview parsing anchor changed'
a=a.replace(old,new,1)

# Frontend: make both allowed orders explicit in the appropriate upload mode.
anchor="wrap.querySelector('#sample').textContent='填入当前账号模板';"
assert j.count(anchor)==1,'Import UI sample anchor changed'
hint=r"""// Both column orders are accepted in balance, recharge and withdrawal.
if(importMode==='balance'){
 wrap.querySelector('#importText').placeholder='余额格式：rjh185185 10000.75\n或 10000.75 rjh185185\n也支持：rjh185185\t\t10000.75';
}else if(importMode==='daily'){
 wrap.querySelector('#importText').placeholder='当日提现：账号 金额，或 金额 账号\n例如 500 rjh185185';
}else if(importMode==='recharge'){
 wrap.querySelector('#importText').placeholder='当日充值：账号 金额，或 金额 账号\n例如 10000.75 rjh185185';
}
"""
j=j.replace(anchor,hint+anchor,1)
assert 'def berlin_finance_row_order(' in a
assert 'berlin_finance_row_order(lines' in a
ap.write_text(a,encoding='utf-8')
jp.write_text(j,encoding='utf-8')
