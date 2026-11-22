"""Berlin-only: amount-first recharge/withdrawal records.

New formats:
  amount / Chinese description / account
  amount / account
  amount<TAB>account (where account contains non-numeric account characters)
Original description/account/amount and account/amount remain intact.
All event formats use existing cents, same-account summation and daily snapshots.
"""

# Strip whitespace and trailing empty Excel columns; keep one-row tab copies.
old = "        else:\n            cells=[str(row).replace('\\ufeff','').strip()]"
new = """        else:
            raw=str(row).replace('\ufeff','')
            cells=([piece.strip() for piece in raw.split('\t')]
                   if '\t' in raw else [raw.strip()])
            while cells and not cells[-1]:cells.pop()"""
assert a.count(old)==1, f"Cashflow text parser changed: {a.count(old)}"
a=a.replace(old,new,1)

anchor="        # Only a one-cell Chinese descriptor may start a triplet; other records\n"
assert a.count(anchor)==1, f"Cashflow parser anchor changed: {a.count(anchor)}"
addition=r'''        # Reversed transaction export: amount, optional Chinese memo, account.
        money_pattern=r'[+-]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?'
        reverse_line=(len(cells)==1 and re.fullmatch(money_pattern,label))
        reverse_pair=(len(cells)==2 and
            re.fullmatch(money_pattern,cells[0]) and
            re.fullmatch(account_pattern,cells[1]) and
            re.search(r'[A-Za-z_.-]',cells[1]))
        if reverse_line or reverse_pair:
            if reverse_pair:
                amount=cells[0]
                account=cells[1]
                account_line=line_no
                advance=1
            else:
                amount=label
                nextpos=pos+1
                if nextpos>=len(nonblank):
                    raise HTTPException(400,f'第{line_no}行金额后缺少会员账号')
                memo_cells=nonblank[nextpos][1]
                if (len(memo_cells)==1 and
                    re.search(r'[\u3400-\u9fff]',memo_cells[0]) and
                    not re.search(r'[\s\t,，;；|]',memo_cells[0])):
                    nextpos+=1
                if nextpos>=len(nonblank):
                    raise HTTPException(400,f'第{line_no}行金额后缺少会员账号')
                account_line,account_cells=nonblank[nextpos]
                if len(account_cells)!=1:
                    raise HTTPException(400,f'第{account_line}行会员账号格式错误')
                account=account_cells[0]
                advance=nextpos-pos+1
            if not re.fullmatch(account_pattern,account):
                raise HTTPException(400,f'第{account_line}行会员账号格式错误')
            try:
                cents=berlin_import_amount_cents(amount)
            except HTTPException:
                raise HTTPException(400,f'第{line_no}行 {account} 金额格式错误')
            if mode=='recharge' and cents<0:
                raise HTTPException(400,f'第{line_no}行 {account} 充值金额不能为负数')
            if mode=='daily':cents=abs(cents)
            key=account.casefold()
            if key in aggregate:
                repeat_count+=1
                aggregate[key]['cents']+=cents
                aggregate[key]['account']=account
            else:
                aggregate[key]={'account':account,'cents':cents}
            event_count+=1
            pos+=advance
            continue
'''
a=a.replace(anchor,addition+anchor,1)

old="支持三行提现记录：第一行中文说明（忽略）、第二行会员账号、第三行提现金额。多笔同账号提现先合计；三行记录中的正数表示实际提现。原两列「账号+金额」仍按旧规则：负数表示提现，正数表示回流。"
new="支持提现流水：说明/账号/金额，或金额/说明/账号，或金额/账号。说明忽略，同账号多笔合计，金额在前时正数表示实际提现。传统两列表格「账号+金额」仍按旧规则：负数提现、正数回流。"
assert j.count(old)==1, f"Withdrawal UI anchor changed: {j.count(old)}"
j=j.replace(old,new,1)
old="支持三行充值记录：第一行中文说明（忽略）、第二行会员账号、第三行金额；同账号多笔自动合计。也支持原来的账号+金额两列表格。"
new="支持充值流水：说明/账号/金额，或金额/说明/账号，或金额/账号；说明自动忽略，同账号多笔合计。原账号+金额两列表格也继续支持。"
assert j.count(old)==1, f"Recharge UI anchor changed: {j.count(old)}"
j=j.replace(old,new,1)
assert j.count("三行交易记录：")==1 and j.count("三行提现记录：")==1
j=j.replace("三行交易记录：","交易流水记录：",1).replace("三行提现记录：","提现流水记录：",1)

assert "if reverse_line or reverse_pair:" in a
assert "berlin_three_line_cashflow(lines,'recharge')" in a
assert "berlin_three_line_cashflow(lines,'daily')" in a
ap.write_text(a,encoding='utf-8')
jp.write_text(j,encoding='utf-8')
