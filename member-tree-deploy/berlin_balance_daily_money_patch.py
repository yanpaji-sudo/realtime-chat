"""Berlin-only: accept signed, precise financial amounts for balance/daily imports.
Existing DB stores cents; round HALF_UP to two decimal places. Other manual
member/summary validation stays unchanged.
"""
old = "def parse_lines(lines, mode):"
assert a.count(old) == 1, "Expected one financial import parser"
helper = '''def berlin_import_amount_cents(raw_value):
    """Signed external balance and withdrawal amounts, rounded safely to cents."""
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    import unicodedata
    amount = unicodedata.normalize('NFKC', str(raw_value)).strip()
    amount = amount.replace('￥', '').replace('¥', '').replace('元', '').strip()
    if ',' in amount:
        if not re.fullmatch(r'[+-]?\d{1,3}(?:,\d{3})+(?:\.\d{1,18})?', amount):
            raise HTTPException(400, '金额千分位格式错误')
        amount = amount.replace(',', '')
    if not re.fullmatch(r'[+-]?(?:\d{1,12}(?:\.\d{1,18})?|\.\d{1,18})(?:[eE][+-]?\d{1,2})?', amount):
        raise HTTPException(400, '金额必须是数字；支持负数和高精度小数')
    try:
        val = Decimal(amount)
        if not val.is_finite() or abs(val) >= Decimal('1000000000000'):
            raise ValueError('金额超出范围')
        result = int((val * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        if abs(result) >= 100000000000000:
            raise ValueError('金额超出范围')
        return result
    except (InvalidOperation, ValueError, OverflowError):
        raise HTTPException(400, '金额格式不正确或超出允许范围')


'''
a = a.replace(old, helper + old, 1)
old = 'values = [cents(v) for v in parts[1:]]'
new = 'values = [berlin_import_amount_cents(v) for v in parts[1:]]'
assert a.count(old) == 1, "Expected one balance/daily monetary parser"
a = a.replace(old, new, 1)
old = '金额格式错误（不能有负数或超过两位小数）'
new = '金额格式错误（请填写有效数字；支持负数及多位小数，系统按两位小数四舍五入）'
assert a.count(old) == 1, "Expected outdated import validation error"
a = a.replace(old, new, 1)
assert 'values = [cents(v) for v in parts[1:]]' not in a
assert 'def cents(value):' in a  # manual/other monetary controls unchanged
ap.write_text(a,encoding='utf-8')
