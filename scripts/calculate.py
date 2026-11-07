#!/usr/bin/env python3
"""Simple, offline, deterministic per-order known-cost contribution calculator.

Read JSON from stdin; emit JSON to stdout. No third-party dependencies or persistence.
"""
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal('0.01')

class InputError(ValueError):
    pass


def decimal_value(raw, label):
    if isinstance(raw, bool) or raw is None or isinstance(raw, (dict, list)):
        raise InputError(f'{label} 必须为明确的数字')
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        raise InputError(f'{label} 不是有效数字')
    if not value.is_finite():
        raise InputError(f'{label} 不能为非有限数')
    return value


def money(raw, label):
    value = decimal_value(raw, label)
    if value < 0:
        raise InputError(f'{label} 不能是负数')
    if value != value.quantize(CENT):
        raise InputError(f'{label} 只能保留至分')
    return value


def rate_value(raw, label):
    if isinstance(raw, str) and raw.strip().endswith('%'):
        value = decimal_value(raw.strip()[:-1], label) / 100
    else:
        value = decimal_value(raw, label)
    if not (Decimal('0') <= value < Decimal('1')):
        raise InputError(f'{label} 必须在 0%（含）至 100%（不含）之间；如 5% 请写 5% 或 0.05')
    return value


def yuan(value):
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def evaluate(data):
    if not isinstance(data, dict):
        raise InputError('输入必须是 JSON 对象')
    name = data.get('scenario') or '当前商品'
    if not isinstance(name, str) or len(name) > 200:
        raise InputError('scenario 应为不超过 200 字的名称')
    if 'seller_revenue' not in data:
        return {'status':'insufficient','missing':['卖家实际确认收入'],'message':'不能推算已知贡献额，请明确收入口径'}
    revenue = money(data['seller_revenue'], 'seller_revenue')
    costs = data.get('costs', [])
    fees = data.get('percentage_fees', [])
    if not isinstance(costs, list) or not isinstance(fees, list):
        raise InputError('costs 和 percentage_fees 必须是数组')
    if not costs and not fees:
        return {'status':'insufficient','missing':['至少一项明确成本/费用'],'message':'未知费用不能默认作零'}
    if len(costs) + len(fees) > 200:
        raise InputError('单次最多处理 200 个费用条目')
    keys = set()
    fixed = Decimal('0')
    cost_rows = []
    percentage_rows = []
    percentage_sum = Decimal('0')
    for index, item in enumerate(costs):
        if not isinstance(item, dict):
            raise InputError('costs 条目必须为对象')
        cname = item.get('name')
        if not isinstance(cname, str) or not cname.strip():
            raise InputError(f'costs[{index}].name 不能为空')
        cname = cname.strip()
        if len(cname) > 100 or cname.casefold() in keys:
            raise InputError(f'存在重复或过长费用名称：{cname}')
        keys.add(cname.casefold())
        amount = money(item.get('amount'), cname)
        fixed += amount
        cost_rows.append({'name':cname,'amount':yuan(amount)})
    variable = Decimal('0')
    for index, item in enumerate(fees):
        if not isinstance(item, dict):
            raise InputError('percentage_fees 条目必须为对象')
        fname = item.get('name')
        if not isinstance(fname, str) or not fname.strip():
            raise InputError(f'percentage_fees[{index}].name 不能为空')
        fname = fname.strip()
        if len(fname)>100 or fname.casefold() in keys:
            raise InputError(f'存在重复或过长费用名称：{fname}')
        keys.add(fname.casefold())
        if item.get('base') != 'seller_revenue':
            raise InputError(f'{fname} 的计费基数不支持：仅允许 seller_revenue')
        rate = rate_value(item.get('rate'), fname)
        charge = (revenue * rate).quantize(CENT, rounding=ROUND_HALF_UP)
        percentage_sum += rate
        variable += charge
        percentage_rows.append({'name':fname,'rate':str(rate),'base':'seller_revenue','amount':yuan(charge)})
    total = fixed + variable
    contribution = revenue - total
    answer = {
      'status':'ok', 'scenario':name, 'result_type':'已知费用范围内单笔贡献测算',
      'currency':'CNY', 'seller_revenue':yuan(revenue), 'costs':cost_rows,
      'percentage_fees':percentage_rows, 'fixed_cost_total':yuan(fixed),
      'percentage_fee_total':yuan(variable), 'known_cost_total':yuan(total),
      'known_contribution':yuan(contribution),
      'known_contribution_rate':None if revenue==0 else str((contribution / revenue * 100).quantize(CENT, rounding=ROUND_HALF_UP))+'%',
      'warning':'本结果仅扣除用户列出的费用，不代表净利润；未提供的费用不是零。'
    }
    if percentage_sum < 1:
        threshold = (fixed/(Decimal('1')-percentage_sum)).quantize(CENT, rounding=ROUND_HALF_UP)
        # Round upward until per-item fee rounding and contribution actually meet the threshold.
        for _ in range(1000):
            fee_total = sum(((threshold * rate_value(x['rate'], x['name'])).quantize(CENT, rounding=ROUND_HALF_UP) for x in percentage_rows),Decimal('0'))
            if threshold >= fixed + fee_total:
                break
            threshold += CENT
        else:
            raise InputError('保本阈值迭代超限，请人工复核本情景')
        answer['known_cost_breakeven_seller_revenue']=yuan(threshold)
        answer['breakeven_note']='仅在已列费用结构及计费基数不变时成立；不是商品标价或完整净利润保本点'
    else:
        answer['known_cost_breakeven_seller_revenue']=None
        answer['breakeven_note']='费率合计达到或超过 100%，不存在可由本公式求出的保本收入'
    return answer


def main():
    try:
        doc = json.load(sys.stdin)
        result = evaluate(doc)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (InputError, ValueError, json.JSONDecodeError, OverflowError) as exc:
        print(json.dumps({'status':'error','message':str(exc)},ensure_ascii=False))
        sys.exit(2)

if __name__=='__main__':
    main()
