"""Live view of a worker run: goal box, step trace, latest screenshot, approval prompts, final report.
Run: streamlit run ui/streamlit_app.py     (start the services first: python scripts/dev_up.py)

The UI never talks to the agent directly. It starts `python -m worker.cli --ui` as a subprocess and only
reads/writes files in runs/<id>/ (trace.jsonl, screenshots, question.json, answer.json, result.json).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
st.set_page_config(page_title='AutoFlow_AI', layout='wide')
st.title('AutoFlow_AI')
st.caption('Autonomous AI task worker')


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return rows


with st.sidebar:
    goal = st.text_area('Task', height=140,
                        value='Find the latest invoice from Acme Supplies and enter it in FinanceDesk.')
    approve = st.selectbox('Ask me before', ['auto', 'writes', 'all'], index=0,
                           help='auto: only irreversible or low-confidence actions. writes: also commit buttons '
                                'and POSTs. all: every write.')
    mock = st.checkbox('Offline scripted policy (no API key, plumbing demo only)')
    if st.button('Run task', type='primary'):
        run_dir = ROOT / 'runs' / time.strftime('ui-%Y%m%d-%H%M%S')
        cmd = [sys.executable, '-m', 'worker.cli', '--ui', '--run-dir', str(run_dir), '--approve', approve, goal]
        if mock:
            cmd.insert(3, '--mock')
        run_dir.mkdir(parents=True, exist_ok=True)
        log = open(run_dir / 'cli.log', 'w')
        st.session_state['proc'] = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        st.session_state['run_dir'] = str(run_dir)
        st.rerun()

run_dir = Path(st.session_state['run_dir']) if 'run_dir' in st.session_state else None
if run_dir is None:
    st.info('Enter a task and press Run task.')
    st.stop()

proc = st.session_state.get('proc')
running = proc is not None and proc.poll() is None
result_path = run_dir / 'result.json'
rows = [r for r in read_jsonl(run_dir / 'trace.jsonl') if r.get('kind') in ('tool', 'note', 'ask', 'answer', 'verify')]

left, right = st.columns([3, 2])
with left:
    st.subheader('Live trace' + ('  (running...)' if running else ''))
    for r in rows:
        k = r['kind']
        if k == 'tool':
            res = r.get('result') or {}
            icon = 'OK ' if res.get('ok') else 'ERR'
            retry = f" (attempt {r['attempt']})" if r.get('attempt', 1) > 1 else ''
            err = '' if res.get('ok') else f" [{r.get('error_class')}]"
            st.text(f"{icon} step {r['step']:>2}  {r['tool']}  {json.dumps(r.get('args'))[:90]}{err}{retry}")
        elif k == 'note':
            st.caption(f"model: {r['text'][:200]}")
        elif k == 'ask':
            st.warning(f"Agent asked: {r['question']}")
        elif k == 'verify':
            st.info(f"Verification: {r['result']}")

with right:
    shots = sorted(run_dir.glob('shot_*.png'))
    if shots:
        st.subheader('Latest screenshot')
        st.image(str(shots[-1]))
    q_path, a_path = run_dir / 'question.json', run_dir / 'answer.json'
    if q_path.exists() and not a_path.exists():
        q = json.loads(q_path.read_text())
        st.error(q['question'])
        if q.get('options'):
            for opt in q['options']:
                if st.button(opt, key=f'opt-{opt}'):
                    a_path.write_text(json.dumps({'answer': opt}))
                    st.rerun()
        else:
            txt = st.text_input('Your answer')
            if st.button('Send') and txt:
                a_path.write_text(json.dumps({'answer': txt}))
                st.rerun()

if result_path.exists():
    rep = json.loads(result_path.read_text())
    st.divider()
    badge = {'done': 'success', 'partial': 'warning', 'blocked': 'error'}.get(rep['status'], 'info')
    getattr(st, badge)(f"**{rep['status'].upper()}**: {rep['summary']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Verified', 'yes' if rep['verification_passed'] else 'NO')
    c2.metric('Steps', rep['steps'])
    c3.metric('Retries', rep['retries'])
    c4.metric('Questions', rep['questions_asked'])
    st.subheader('Independent verification')
    for v in rep['verified']:
        mark = {True: 'PASS', False: 'FAIL', None: 'judge'}[v['match']]
        st.text(f"[{mark}] {v['criterion']}  ->  {v['observed'][:120]}")
    if rep['weak_verification']:
        st.caption('Note: no exact checks were defined, so verification relied on the judge only.')
    with st.expander('Facts the agent extracted'):
        st.json(rep['facts'])
    with st.expander('Evidence files'):
        for p in rep['evidence']:
            st.text(p)
elif running:
    time.sleep(1)
    st.rerun()
else:
    st.error('The run ended without a result. See ' + str(run_dir / 'cli.log'))
