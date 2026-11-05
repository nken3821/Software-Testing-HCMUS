# STLab02 – Test Case Execution (EduCommerce)

Data-driven testing of the in-memory EduCommerce checkout module (Python 3.10+).
Selected requirements (not used in the Instruction worked examples): **REQ-02, 04, 07, 09, 10, 12, 14, 15, 16** (9 REQ, 6 modules).

| Item | Count |
|---|---|
| Conditions / Scenarios / Test cases | 23 / 22 / 38 (21 negative or boundary) |
| Run on original app | 38 executed – 35 PASS, 3 FAIL, 0 BLOCKED |
| Retest on fixed app | 38 executed – 38 PASS |

## Layout
```
ecommerce_app.py          application under test (UNCHANGED from the Instruction)
ecommerce_app_fixed.py    copy with fixes, used only for retest/regression
test_cases.csv            38 data-driven cases (expected derived from acceptance criteria)
build_test_cases.py       regenerates test_cases.csv + design/*.csv
test_runner.py            fixture, CSV reader, dispatcher, verification, CSV/Excel/HTML report
gradio_dashboard.py       optional Gradio dashboard (chart beside table)
problem_solving_demos.py  executable evidence for Part 3 (3.2, 3.4, 3.6, 3.7)
design/                   requirement analysis, conditions, scenarios
reports/                  run on ORIGINAL app (test_execution.csv, test_report.xlsx, test_dashboard.html, demos json)
reports_after_fix/        retest on FIXED app
STLab02_Colab.ipynb       notebook that runs everything on Google Colab
```

## Run from a clean environment
```bash
git clone <this repo> && cd <repo>
pip install -r requirements.txt
python test_runner.py                                   # original app  -> reports/
python test_runner.py --app ecommerce_app_fixed --out reports_after_fix   # retest
python problem_solving_demos.py                         # Part 3 evidence
python gradio_dashboard.py reports                      # optional dashboard
```
Google Colab: upload the repo files (or `!git clone`), then open `STLab02_Colab.ipynb` and Run all.

## Statuses
* **PASS** – return value and state (stock, orders, charges, used_codes) match expected.
* **FAIL** – at least one expected value differs from actual (expected is never edited to match the app).
* **BLOCKED** – case cannot run (bad JSON, unknown fixture/operation/expected key, runner error). Never silently skipped; the report shows completeness = executed / rows in CSV.

## Defects found (details in the PDF report)
* DEF-001 `Cart.add` accepts `True` as quantity (REQ-02, low, needs BA confirmation).
* DEF-002 `Checkout.place` reserves stock before validating the payment method, so an invalid method leaks stock (REQ-16, major).
