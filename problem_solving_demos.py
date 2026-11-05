"""Executable evidence for Part 3 (3.4 price change, 3.6 shared state, 3.7 data completeness, 3.2 voucher sequence)."""
import csv, json, tempfile
from pathlib import Path
import ecommerce_app as app
from ecommerce_app import D
import test_runner as tr

out = {}

# 3.4 price changes between add-to-cart and checkout
svc, cust, cart = app.fixture('600k')
sub_at_add = cart.subtotal()
svc.catalog.products['A'].price = D(250000)          # price changed after add-to-cart
o = svc.place(cust, cart, voucher='SAVE10', key='P34')
out['3.4_price_change'] = {'subtotal_at_add_to_cart': f'{sub_at_add:.0f}', 'price_A_after_change': '250000',
                           'order_total': f'{o.total:.0f}', 'discount': f'{o.discount:.0f}',
                           'note': 'Cart.subtotal() reads catalog price LIVE -> price is not locked at add-to-cart'}

# 3.6 shared fixture vs isolated fixture
shared = app.fixture('500k')
svc, cust, cart = shared
svc.catalog.products['B'].price = D(299999)           # case 1 mutates price (like fixture '499999')
svc.place(cust, cart, key='X1')                       # case 1 consumes stock
shared_case2_subtotal = cart.subtotal()               # case 2 expects 500000
shared_stock_A = svc.catalog.products['A'].stock
iso_subtotal = app.fixture('500k')[2].subtotal()
iso_stock_A = app.fixture('500k')[0].catalog.products['A'].stock
out['3.6_shared_state'] = {'case2_subtotal_shared': f'{shared_case2_subtotal:.0f}', 'case2_subtotal_isolated': f'{iso_subtotal:.0f}',
                           'stock_A_shared_after_case1': shared_stock_A, 'stock_A_isolated': iso_stock_A}

# 3.7 CSV with 20 rows, 3 corrupted JSON rows
import ecommerce_app_fixed as fixed_app   # fixed app => 17 valid rows all PASS, like the scenario in 3.7
rows = tr.read_cases(Path('test_cases.csv'))[:20]
for i in (4, 9, 14): rows[i]['expected_json'] = '{broken json'
naive_pass = 0
for r in rows:
    try: tr.parse_row(r)
    except Exception: continue                        # naive runner: silently skips bad rows
    res = tr.execute_case(fixed_app, r, 'DEMO')
    naive_pass += res['execution_status'] == 'PASS'
ours = [tr.execute_case(fixed_app, r, 'DEMO')['execution_status'] for r in rows]
from collections import Counter
c = Counter(ours)
out['3.7_completeness'] = {'rows_in_csv': 20, 'naive_runner_executed_PASS': naive_pass, 'naive_report': f'{naive_pass}/{naive_pass} = 100% (misleading)',
                           'our_runner': dict(c), 'our_completeness_pct': round(100 * (c['PASS'] + c['FAIL']) / 20, 1),
                           'our_pass_rate_of_all_rows_pct': round(100 * c['PASS'] / 20, 1)}

# 3.2 voucher state sequence on ORIGINAL app: decline -> then retry with approval
svc, cust, cart = app.fixture('600k')
seq = []
try: svc.place(cust, cart, voucher='SAVE10', method='ONLINE', approved=False, key='S1')
except ValueError as e: seq.append(('declined', str(e), sorted(cust.used_codes)))
o = svc.place(cust, cart, voucher='SAVE10', method='ONLINE', approved=True, key='S2')
seq.append(('retry_approved', o.status, sorted(cust.used_codes)))
out['3.2_voucher_sequence'] = seq

Path('reports').mkdir(exist_ok=True)
Path('reports/problem_solving_demos.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
print(json.dumps(out, indent=1, ensure_ascii=False))
