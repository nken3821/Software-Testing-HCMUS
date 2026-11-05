"""STLab02 - data-driven test runner for EduCommerce.
CSV -> fixture -> dispatcher -> compare expected/actual (return value AND state) -> PASS/FAIL/BLOCKED -> reports.

Usage:  python test_runner.py [--cases test_cases.csv] [--out reports] [--app ecommerce_app]
"""
import argparse, csv, datetime, html, importlib, json, time
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
REQUIRED_COLS = ['test_case_id', 'requirement_id', 'condition_id', 'scenario_id', 'title', 'priority', 'precondition',
                 'fixture_key', 'input_json', 'expected_type', 'expected_json', 'execution_status', 'actual_result',
                 'error_message', 'evidence_reference']
APP_FIXTURES = {'600k', '500k', '300k', '1000k', '1500k', '499999'}


class Blocked(Exception):
    """Test cannot be executed (bad data / unknown fixture / unsupported check) -> BLOCKED, never silently skipped."""


# ------------------------------------------------------------------ E04: input reader + schema validation
def read_cases(path):
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing: raise ValueError(f'SCHEMA_MISSING_COLUMNS: {missing}')
    dup = df.test_case_id[df.test_case_id.duplicated()].tolist()
    if dup: raise ValueError(f'DUPLICATE_TEST_IDS: {dup}')
    return df.to_dict('records')


def parse_row(row):
    try:
        return json.loads(row['input_json']), json.loads(row['expected_json'])
    except json.JSONDecodeError as exc:
        raise Blocked(f'BAD_JSON: {exc}')


# ------------------------------------------------------------------ E03: fixture - fresh isolated state per case
def build_fixture(app, key, inp):
    """Returns (service, customer, cart). Every call creates NEW Checkout/Customer/Cart objects (test isolation)."""
    if key in APP_FIXTURES: return app.fixture(key)          # fixtures defined by the application module
    service = app.Checkout(); customer = app.Customer('U_NEW'); cart = app.Cart(service.catalog)
    if key == 'empty': pass                                   # empty cart, authenticated user
    elif key == 'unauth_600k': customer.authenticated = False; cart.add('A', 3)
    elif key == 'used_save10_600k': customer.used_codes.add('SAVE10'); cart.add('A', 3)
    else: raise Blocked(f'UNKNOWN_FIXTURE: {key}')
    for sku, qty in inp.get('cart', []): cart.add(sku, qty)  # extra lines requested by the test data
    return service, customer, cart


def snapshot(svc, cust):
    return {'stock': {k: p.stock for k, p in svc.catalog.products.items()}, 'orders': len(svc.orders),
            'used_codes': sorted(cust.used_codes), 'charges': len(svc.payments.charges),
            'charge_amounts': [f"{c['amount']:.0f}" for c in svc.payments.charges]}


def call(fn, *a, **kw):
    """Run business function; return (value, error_code). Only ValueError is a business error; others are UNEXPECTED."""
    try: return fn(*a, **kw), ''
    except ValueError as exc: return None, str(exc)
    except Exception as exc: return None, f'UNEXPECTED:{type(exc).__name__}:{exc}'


# ------------------------------------------------------------------ E05: dispatcher - which function each case calls
def dispatch(app, svc, cust, cart, inp, case_id):
    op = inp.get('op'); view = {}
    if op == 'cart_add':                                       # Cart.add / Cart.subtotal
        err = ''
        for sku, qty in inp['adds']:
            _, err = call(cart.add, sku, qty)
            if err: break
        view.update(error=err, lines=[[x.sku, x.quantity] for x in cart.lines], subtotal=f'{cart.subtotal():.0f}')
    elif op == 'shipping':                                     # Shipping.calculate
        fee, err = call(svc.shipping.calculate, app.D(inp['subtotal']), inp['area'])
        view.update(error=err, fee='' if fee is None else f'{fee:.0f}')
    elif op == 'place':                                        # Checkout.place (1..n sequential calls)
        outs = []
        for i, c in enumerate(inp['calls']):
            kw = {'area': 'inner', 'voucher': None, 'method': 'COD', 'approved': True, 'key': f'{case_id}-{i}'}; kw.update(c)
            order, err = call(svc.place, cust, cart, **kw)
            o = {'error': err}
            if order: o.update(status=order.status, order_id=order.order_id, total=f'{order.total:.0f}',
                               discount=f'{order.discount:.0f}', shipping=f'{order.shipping:.0f}')
            outs.append(o)
        last = outs[-1]
        view.update(error=last['error'], errors=[o['error'] for o in outs], outcomes=outs)
        for k in ('status', 'total', 'discount', 'shipping'):
            if k in last: view[k] = last[k]
        ids = [o['order_id'] for o in outs if 'order_id' in o]
        view['order_ids_unique'] = len(ids) == len(set(ids)) and len(ids) > 0
    else:
        raise Blocked(f'UNKNOWN_OPERATION: {op}')
    return view


# ------------------------------------------------------------------ E06: verification of return value + state, status
def verify(expected, view, before, after):
    state = snapshot_view(before, after)
    full = {**view, **state}
    problems = []
    for k, exp in expected.items():
        if k not in full: raise Blocked(f'UNSUPPORTED_EXPECTED_KEY: {k}')
        if full[k] != exp: problems.append(f'{k}: expected {exp!r} actual {full[k]!r}')
    return problems


def snapshot_view(before, after):
    delta = {k: after['stock'][k] - before['stock'][k] for k in before['stock']}
    return {'stock_unchanged': before['stock'] == after['stock'], 'stock_delta': {k: v for k, v in delta.items() if v},
            'orders': after['orders'], 'used_codes': after['used_codes'], 'charges': after['charges'],
            'charge_amounts': after['charge_amounts']}


def execute_case(app, row, run_id):
    t0 = time.perf_counter(); status, msg, actual, evidence = 'BLOCKED', '', {}, {}
    try:
        inp, expected = parse_row(row)
        svc, cust, cart = build_fixture(app, row['fixture_key'], inp)
        before = snapshot(svc, cust)
        view = dispatch(app, svc, cust, cart, inp, row['test_case_id'])
        after = snapshot(svc, cust)
        problems = verify(expected, view, before, after)
        actual = {k: v for k, v in {**view, **snapshot_view(before, after)}.items() if k in expected or k in ('error', 'status')}
        evidence = {'stock_before': before['stock'], 'stock_after': after['stock'], 'orders': after['orders'],
                    'used_codes': after['used_codes'], 'charges': after['charges'], 'outcomes': view.get('outcomes', [])}
        status, msg = ('PASS', '') if not problems else ('FAIL', '; '.join(problems))
    except Blocked as exc:
        status, msg = 'BLOCKED', str(exc)
    except Exception as exc:  # setup crash = test-script problem, not a product verdict
        status, msg = 'BLOCKED', f'RUNNER_ERROR: {type(exc).__name__}: {exc}'
    return {**row, 'run_id': run_id, 'execution_status': status, 'actual_result': json.dumps(actual, ensure_ascii=False),
            'error_message': msg, 'evidence_reference': json.dumps(evidence, ensure_ascii=False),
            'duration_ms': round((time.perf_counter() - t0) * 1000, 3),
            'executed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}


# ------------------------------------------------------------------ reporter
def run_suite(cases_path=None, out_dir=None, app_name='ecommerce_app'):
    app = importlib.import_module(app_name)
    cases_path = Path(cases_path or ROOT / 'test_cases.csv'); out = Path(out_dir or ROOT / 'reports'); out.mkdir(parents=True, exist_ok=True)
    rows = read_cases(cases_path); stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    results = [execute_case(app, r, f'RUN-{stamp}-{i + 1:03d}') for i, r in enumerate(rows)]
    df = pd.DataFrame(results)
    df.insert(0, 'app_under_test', app_name)
    assert len(df) == len(rows), 'completeness check failed: some rows were not executed'
    counts = Counter(df.execution_status)
    totals = {'file_rows': len(rows), 'executed': len(df), 'PASS': counts['PASS'], 'FAIL': counts['FAIL'], 'BLOCKED': counts['BLOCKED'],
              'pass_rate_pct': round(100 * counts['PASS'] / len(df), 1), 'completeness_pct': round(100 * len(df) / len(rows), 1),
              'app_under_test': app_name, 'generated_at': datetime.datetime.now().isoformat(timespec='seconds')}
    by_req = df.groupby(['requirement_id', 'execution_status']).size().unstack(fill_value=0)
    for s in ('PASS', 'FAIL', 'BLOCKED'):
        if s not in by_req: by_req[s] = 0
    by_req = by_req[['PASS', 'FAIL', 'BLOCKED']].reset_index(); by_req['total'] = by_req[['PASS', 'FAIL', 'BLOCKED']].sum(axis=1)
    by_req['pass_rate_pct'] = (100 * by_req.PASS / by_req.total).round(1)
    trace = df[['requirement_id', 'condition_id', 'scenario_id', 'test_case_id', 'run_id', 'execution_status']]
    df.to_csv(out / 'test_execution.csv', index=False, encoding='utf-8-sig')
    with pd.ExcelWriter(out / 'test_report.xlsx', engine='openpyxl') as xls:
        df.to_excel(xls, index=False, sheet_name='Execution'); trace.to_excel(xls, index=False, sheet_name='Traceability')
        by_req.to_excel(xls, index=False, sheet_name='Summary_by_REQ'); pd.DataFrame([totals]).to_excel(xls, index=False, sheet_name='Totals')
        for ws in xls.book.worksheets:
            for col in ws.columns: ws.column_dimensions[col[0].column_letter].width = min(48, max(12, max(len(str(c.value or '')) for c in col[:40]) + 2))
            ws.freeze_panes = 'A2'
    (out / 'test_dashboard.html').write_text(render_dashboard(df, by_req, totals), encoding='utf-8')
    (out / 'summary.json').write_text(json.dumps({'totals': totals, 'by_req': by_req.to_dict('records')}, indent=1), encoding='utf-8')
    print(f"[{app_name}] file rows {len(rows)} | executed {len(df)} | PASS {counts['PASS']} | FAIL {counts['FAIL']} | BLOCKED {counts['BLOCKED']} | pass rate {totals['pass_rate_pct']}%")
    for _, r in df[df.execution_status != 'PASS'].iterrows(): print(f"  {r.execution_status:7} {r.test_case_id} ({r.requirement_id}) -> {r.error_message}")
    return df, by_req, totals


def render_dashboard(df, by_req, t):
    colors = {'PASS': '#16a34a', 'FAIL': '#dc2626', 'BLOCKED': '#d97706'}
    bars = []; W = 520; maxn = max(1, int(by_req.total.max()))
    for i, r in by_req.iterrows():
        y = 14 + i * 30; x = 90; bars.append(f'<text x="0" y="{y + 14}" font-size="13">{r.requirement_id}</text>')
        for s in ('PASS', 'FAIL', 'BLOCKED'):
            w = (W - x - 30) * int(r[s]) / maxn
            if w: bars.append(f'<rect x="{x}" y="{y}" width="{w:.1f}" height="20" fill="{colors[s]}"/><text x="{x + w / 2:.1f}" y="{y + 14}" font-size="12" fill="#fff" text-anchor="middle">{int(r[s])}</text>'); x += w
    svg = f'<svg width="{W}" height="{30 * len(by_req) + 20}" font-family="Arial">{"".join(bars)}</svg>'
    rows = ''.join(f'<tr class="{r.execution_status}"><td>{r.test_case_id}</td><td>{r.requirement_id}</td><td>{r.scenario_id}</td><td>{html.escape(r.title)}</td><td>{html.escape(r.expected_json)}</td><td>{html.escape(r.actual_result)}</td><td class="s">{r.execution_status}</td><td>{html.escape(r.error_message)}</td></tr>' for r in df.itertuples())
    reqrows = ''.join(f'<tr><td>{r.requirement_id}</td><td>{r.PASS}</td><td>{r.FAIL}</td><td>{r.BLOCKED}</td><td>{r.total}</td><td>{r.pass_rate_pct}%</td></tr>' for r in by_req.itertuples())
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>EduCommerce STLab02 - Test Dashboard</title><style>
body{{font:14px Arial;margin:28px;color:#14233c}}h1{{color:#17385f;margin:0 0 4px}}.m{{display:inline-block;margin:8px 10px 8px 0;padding:12px 18px;border-radius:10px;background:#edf3f9;font-size:20px}}
.m small{{display:block;font-size:11px;color:#51627a}}table{{border-collapse:collapse;width:100%;margin-top:8px}}td,th{{border:1px solid #cbd5e1;padding:6px 8px;text-align:left;vertical-align:top;font-size:12px}}th{{background:#16385e;color:#fff}}
.row{{display:flex;gap:28px;flex-wrap:wrap;align-items:flex-start}}.row>div{{flex:1;min-width:360px}}tr.FAIL{{background:#fee2e2}}tr.BLOCKED{{background:#fef3c7}}td.s{{font-weight:bold}}button{{margin-right:6px;padding:4px 12px}}
</style></head><body><h1>EduCommerce - STLab02 Test Execution Dashboard</h1><div>App under test: <b>{t['app_under_test']}</b> &middot; generated {t['generated_at']}</div>
<div><span class="m">{t['executed']}<small>executed</small></span><span class="m" style="color:#16a34a">{t['PASS']}<small>PASS</small></span><span class="m" style="color:#dc2626">{t['FAIL']}<small>FAIL</small></span><span class="m" style="color:#d97706">{t['BLOCKED']}<small>BLOCKED</small></span><span class="m">{t['pass_rate_pct']}%<small>pass rate</small></span><span class="m">{t['completeness_pct']}%<small>completeness (executed / rows in CSV)</small></span></div>
<div class="row"><div><h3>Result by requirement</h3>{svg}</div><div><h3>Summary table</h3><table><tr><th>REQ</th><th>PASS</th><th>FAIL</th><th>BLOCKED</th><th>Total</th><th>Pass rate</th></tr>{reqrows}</table></div></div>
<h3>Traceability &amp; execution</h3><div><button onclick="f('ALL')">All</button><button onclick="f('PASS')">PASS</button><button onclick="f('FAIL')">FAIL</button><button onclick="f('BLOCKED')">BLOCKED</button></div>
<table id="t"><tr><th>Case</th><th>REQ</th><th>Scenario</th><th>Title</th><th>Expected</th><th>Actual</th><th>Status</th><th>Mismatch</th></tr>{rows}</table>
<script>function f(s){{document.querySelectorAll('#t tr[class]').forEach(r=>r.style.display=(s=='ALL'||r.className==s)?'':'none')}}</script></body></html>'''


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', default=str(ROOT / 'test_cases.csv')); ap.add_argument('--out', default=str(ROOT / 'reports'))
    ap.add_argument('--app', default='ecommerce_app')
    a = ap.parse_args(); run_suite(a.cases, a.out, a.app)
