"""Optional Gradio dashboard: chart (left) next to table (right). Run after test_runner.py.  pip install gradio matplotlib"""
import sys
import gradio as gr, matplotlib.pyplot as plt, pandas as pd

folder = sys.argv[1] if len(sys.argv) > 1 else 'reports'
df = pd.read_csv(f'{folder}/test_execution.csv').fillna('')
COLORS = {'PASS': '#16a34a', 'FAIL': '#dc2626', 'BLOCKED': '#d97706'}


def view(req='ALL', status='ALL'):
    d = df.copy()
    if req != 'ALL': d = d[d.requirement_id == req]
    if status != 'ALL': d = d[d.execution_status == status]
    s = d.execution_status.value_counts().reindex(['PASS', 'FAIL', 'BLOCKED'], fill_value=0)
    fig, ax = plt.subplots(figsize=(6, 4)); bars = ax.bar(s.index, s.values, color=[COLORS[i] for i in s.index])
    ax.bar_label(bars, padding=3); ax.set_title('Test execution results'); ax.set_ylabel('Test cases'); fig.tight_layout()
    cols = ['test_case_id', 'requirement_id', 'scenario_id', 'expected_json', 'actual_result', 'execution_status', 'error_message']
    return fig, d[cols], f"Executed: {len(d)} | PASS: {s['PASS']} | FAIL: {s['FAIL']} | BLOCKED: {s['BLOCKED']}"


with gr.Blocks(title='EduCommerce - STLab02 Dashboard') as demo:
    gr.Markdown('# EduCommerce - Requirement Traceability & Test Results')
    with gr.Row():
        rq = gr.Dropdown(['ALL'] + sorted(df.requirement_id.unique().tolist()), value='ALL', label='Requirement')
        st = gr.Dropdown(['ALL', 'PASS', 'FAIL', 'BLOCKED'], value='ALL', label='Status')
    line = gr.Markdown()
    with gr.Row(equal_height=True):
        with gr.Column(scale=1, min_width=300): chart = gr.Plot(label='Result distribution')
        with gr.Column(scale=2, min_width=420): table = gr.Dataframe(label='Execution details', interactive=False, wrap=True)
    gr.File(value=f'{folder}/test_report.xlsx', label='Download Excel report')
    for c in (rq, st): c.change(view, [rq, st], [chart, table, line])
    demo.load(view, [rq, st], [chart, table, line])

if __name__ == '__main__':
    demo.launch(share=False)   # use share=True in Colab for a temporary public link
