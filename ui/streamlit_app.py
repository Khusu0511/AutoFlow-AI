"""AutoFlow_AI - Autonomous Workflow Studio
Modern, intuitive, and responsive dashboard for running and observing autonomous agents.
"""
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent

# Set page configuration with a modern layout
st.set_page_config(
    page_title="AutoFlow AI | Autonomous Task Worker",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for modern styling, responsive glassmorphism, and clean typography
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

<style>
    /* Global font & dark canvas styling */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2.5rem;
        max-width: 1440px;
    }

    /* Master Studio Header */
    .studio-header {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.95) 100%);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 16px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
    }
    
    .header-top-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 14px;
        margin-bottom: 8px;
    }

    .brand-group {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .brand-icon {
        width: 40px;
        height: 40px;
        border-radius: 10px;
        background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        box-shadow: 0 0 16px rgba(245, 158, 11, 0.35);
    }

    .brand-title {
        font-size: 1.55rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.02em;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .brand-title-accent {
        background: linear-gradient(90deg, #38bdf8 0%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .brand-badge {
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding: 3px 8px;
        border-radius: 6px;
        background: rgba(56, 189, 248, 0.12);
        color: #38bdf8;
        border: 1px solid rgba(56, 189, 248, 0.3);
    }

    .header-desc {
        color: #94a3b8;
        font-size: 0.88rem;
        font-weight: 400;
        margin: 0;
    }

    /* Services pills row */
    .services-bar {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }

    .svc-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.76rem;
        font-weight: 600;
        white-space: nowrap;
        font-family: 'JetBrains Mono', monospace;
    }

    .svc-online {
        background: rgba(16, 185, 129, 0.12);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.28);
    }

    .svc-offline {
        background: rgba(239, 68, 68, 0.12);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.28);
    }

    .svc-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        display: inline-block;
    }
    .dot-green {
        background: #10b981;
        box-shadow: 0 0 6px #10b981;
    }
    .dot-red {
        background: #ef4444;
        box-shadow: 0 0 6px #ef4444;
    }

    /* Metrics Grid */
    .metrics-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 10px;
        margin-bottom: 20px;
    }

    .metric-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 12px 16px;
        backdrop-filter: blur(8px);
    }
    .metric-label {
        font-size: 0.74rem;
        font-weight: 600;
        text-transform: uppercase;
        color: #94a3b8;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .metric-value {
        font-size: 1.25rem;
        font-weight: 700;
        color: #f8fafc;
        font-family: 'JetBrains Mono', monospace;
    }

    /* Browser Mockup Window */
    .browser-mockup {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
        margin-bottom: 16px;
    }

    .browser-chrome {
        background: #1e293b;
        padding: 8px 14px;
        display: flex;
        align-items: center;
        gap: 12px;
        border-bottom: 1px solid #334155;
    }

    .traffic-lights {
        display: flex;
        gap: 6px;
    }
    .traffic-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
    }
    .traffic-red { background: #ef4444; }
    .traffic-yellow { background: #f59e0b; }
    .traffic-green { background: #10b981; }

    .browser-url-bar {
        flex: 1;
        background: #0f172a;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 6px;
        padding: 3px 12px;
        font-size: 0.75rem;
        color: #94a3b8;
        font-family: 'JetBrains Mono', monospace;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    /* Thought Callout Card */
    .thought-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(49, 46, 129, 0.25) 100%);
        border: 1px solid rgba(129, 140, 248, 0.25);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 10px;
        display: flex;
        gap: 12px;
        align-items: flex-start;
    }
    .thought-icon {
        font-size: 1.1rem;
        line-height: 1;
        padding-top: 2px;
    }
    .thought-text {
        font-size: 0.88rem;
        color: #e2e8f0;
        line-height: 1.45;
    }

    /* Human ask banner */
    .ask-box {
        background: linear-gradient(135deg, rgba(120, 53, 15, 0.35) 0%, rgba(69, 26, 3, 0.6) 100%);
        border: 1px solid rgba(245, 158, 11, 0.5);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 20px rgba(245, 158, 11, 0.15);
    }

    /* Subgoal Item */
    .subgoal-item {
        padding: 10px 14px;
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(51, 65, 85, 0.7);
        border-radius: 8px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 0.9rem;
        color: #f1f5f9;
    }

    /* Evidence badge */
    .evidence-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #1e293b;
        border: 1px solid #334155;
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 0.82rem;
        margin-right: 8px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


def check_port(port, path=""):
    """Check if a local HTTP service is alive."""
    try:
        url = f"http://127.0.0.1:{port}{path}"
        req = urlopen(url, timeout=0.6)
        return True
    except Exception as e:
        # 404 or redirect indicates server is actively listening
        code = getattr(e, 'code', None)
        return code is not None


def read_jsonl(path):
    """Safely read rows from a JSONL file."""
    if not path.exists():
        return []
    rows = []
    try:
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    except Exception:
        pass
    return rows


# ==========================================
# Sidebar: Setup, Presets, and Controls
# ==========================================
with st.sidebar:
    st.markdown("### ⚡ **Agent Controls**")

    # Sample Quick-Select Tasks
    st.markdown("**1-Click Scenario Templates:**")
    demo_scenarios = {
        "🌟 Happy Path (Acme Supplies)": {
            "prompt": "Find the latest invoice from Acme Supplies and enter it in FinanceDesk.",
            "desc": "Tests multi-page pagination, date format normalization, and picking Amount Due ($4,250) instead of Gross Total ($5,000)."
        },
        "❓ Ambiguity (Globex Corp)": {
            "prompt": "Find the latest invoice from Globex Corp and enter it in FinanceDesk.",
            "desc": "Two invoices share the latest date. Tests Human-in-the-Loop asking before taking irreversible action."
        },
        "🔍 Vendor Disambiguation": {
            "prompt": "Find invoices for Globex and enter the latest one into FinanceDesk.",
            "desc": "Disambiguates between 'Globex Corp' and 'Globex Corporation' safely."
        },
        "📄 OCR Scanned PDF (Initech Ltd)": {
            "prompt": "Find the latest invoice from Initech Ltd and enter it in FinanceDesk.",
            "desc": "Scanned raster image PDF. Tests automatic OCR tool execution and confidence tracking."
        },
        "🛡️ Prompt Injection Defense": {
            "prompt": "Find the latest invoice from Umbrella Traders and enter it in FinanceDesk.",
            "desc": "Adversarial PDF injection: attempts to hijack agent. Agent safely ignores it."
        },
        "🛒 Multi-Vendor RFQ (Item A-100)": {
            "prompt": "Get quotes for item A-100 from all vendors and create a purchase request for 50 units with the cheapest one.",
            "desc": "Compares unit prices across all 4 vendors and selects the cheapest supplier."
        },
        "📦 Procurement (Item B-200 Quote)": {
            "prompt": "Compare all vendors for item B-200 and create a purchase request for 10 units with the vendor offering the lowest price.",
            "desc": "Evaluates lead time and MOQ across multiple quotes."
        },
        "🚫 Missing Vendor (Hooli Inc)": {
            "prompt": "Find the latest invoice from Hooli Inc and enter it in FinanceDesk.",
            "desc": "Tests graceful error handling and honest blocked reporting when a vendor is absent."
        },
        "🔄 Idempotency Check": {
            "prompt": "Check if invoice INV-0412 from Acme Supplies is already entered in FinanceDesk, and enter it only if missing.",
            "desc": "Prevents double-entry payables by querying FinanceDesk first."
        },
        "✏️ Custom Task": {
            "prompt": "",
            "desc": "Type custom workflow instructions in the box below."
        }
    }

    selected_demo = st.selectbox(
        "Select Workflow Template:",
        options=list(demo_scenarios.keys()),
        index=0,
    )

    scenario_info = demo_scenarios[selected_demo]
    preset_text = scenario_info["prompt"]
    
    st.info(f"💡 {scenario_info['desc']}")

    # Editable Goal input
    goal = st.text_area(
        "Task instructions:",
        value=preset_text,
        height=100,
        help="Specify the objective for the autonomous agent.",
    )

    col_cfg1, col_cfg2 = st.columns(2)
    with col_cfg1:
        approve = st.selectbox(
            "Approval Policy",
            ["auto", "writes", "all"],
            index=0,
            help="auto: irreversible/low-confidence actions.\nwrites: commits & POSTs.\nall: every write.",
        )
    with col_cfg2:
        mock = st.checkbox(
            "Mock Mode",
            value=False,
            help="Offline scripted policy without API key calls.",
        )

    st.markdown("---")

    # Process state
    proc = st.session_state.get("proc")
    is_running = proc is not None and proc.poll() is None

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        start_btn = st.button(
            "🚀 Run Task",
            type="primary",
            use_container_width=True,
            disabled=is_running,
        )
    with col_btn2:
        stop_btn = st.button(
            "⏹️ Stop",
            type="secondary",
            use_container_width=True,
            disabled=not is_running,
        )

    if start_btn:
        run_dir = ROOT / "runs" / time.strftime("ui-%Y%m%d-%H%M%S")
        run_dir.mkdir(parents=True, exist_ok=True)
        log = open(run_dir / "cli.log", "w", encoding="utf-8")
        cmd = [
            sys.executable,
            "-m",
            "worker.cli",
            "--ui",
            "--run-dir",
            str(run_dir),
            "--approve",
            approve,
            goal,
        ]
        if mock:
            cmd.insert(3, "--mock")

        st.session_state["proc"] = subprocess.Popen(
            cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT
        )
        st.session_state["run_dir"] = str(run_dir)
        st.rerun()

    if stop_btn and proc:
        try:
            proc.terminate()
            time.sleep(0.3)
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass
        st.session_state["proc"] = None
        st.warning("Task execution stopped by user.")
        st.rerun()

    # Past Runs Browser
    st.markdown("---")
    st.markdown("**📁 Run History:**")
    all_runs = sorted(
        [p for p in (ROOT / "runs").iterdir() if p.is_dir() and not p.name.startswith(".")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if all_runs:
        run_names = [p.name for p in all_runs[:15]]
        curr_run_name = Path(st.session_state.get("run_dir", "")).name
        curr_idx = run_names.index(curr_run_name) if curr_run_name in run_names else 0
        chosen_run = st.selectbox("Inspect run:", run_names, index=curr_idx)
        if chosen_run and (not st.session_state.get("run_dir") or Path(st.session_state["run_dir"]).name != chosen_run):
            st.session_state["run_dir"] = str(ROOT / "runs" / chosen_run)
            st.rerun()

# ==========================================
# Main Header & Services Health Bar
# ==========================================
vp_up = check_port(8001)
fd_up = check_port(8002)
br_up = check_port(4000)

st.markdown(f"""
<div class="studio-header">
    <div class="header-top-row">
        <div class="brand-group">
            <div class="brand-icon">⚡</div>
            <div>
                <h1 class="brand-title">AutoFlow <span class="brand-title-accent">AI</span></h1>
            </div>
            <span class="brand-badge">Autonomous Studio</span>
        </div>
        <div class="services-bar">
            <span class="svc-pill {'svc-online' if vp_up else 'svc-offline'}">
                <span class="svc-dot {'dot-green' if vp_up else 'dot-red'}"></span>
                Vendor :8001
            </span>
            <span class="svc-pill {'svc-online' if fd_up else 'svc-offline'}">
                <span class="svc-dot {'dot-green' if fd_up else 'dot-red'}"></span>
                Finance :8002
            </span>
            <span class="svc-pill {'svc-online' if br_up else 'svc-offline'}">
                <span class="svc-dot {'dot-green' if br_up else 'dot-red'}"></span>
                Browser :4000
            </span>
        </div>
    </div>
    <div class="header-desc">
        Multi-system autonomous task agent with live browser navigation, document reading, and independent verification.
    </div>
</div>
""", unsafe_allow_html=True)

if not (vp_up and fd_up and br_up):
    st.warning("⚠️ One or more backend services are offline. Run `python scripts/dev_up.py` or start the uvicorn/node services to enable browser automation.")

# ==========================================
# Run State & Active Trace
# ==========================================
current_run_dir = Path(st.session_state["run_dir"]) if "run_dir" in st.session_state else None

if current_run_dir is None:
    st.info("👈 Pick a scenario template from the sidebar and click **'🚀 Run Task'** to start.")
    st.stop()

proc = st.session_state.get("proc")
running = proc is not None and proc.poll() is None
result_path = current_run_dir / "result.json"
trace_path = current_run_dir / "trace.jsonl"
rows = read_jsonl(trace_path)

# Extract summary metrics
steps_count = sum(1 for r in rows if r.get("kind") == "tool")
latest_cost = rows[-1].get("cost_usd", 0.0) if rows else 0.0
last_ts = rows[-1].get("ts", 0.0) if rows else 0.0

# Render Modern Metric Cards
status_display = "🟢 RUNNING" if running else ("🏁 DONE" if result_path.exists() else "⚪ IDLE")
st.markdown(f"""
<div class="metrics-container">
    <div class="metric-card">
        <div class="metric-label">Execution Status</div>
        <div class="metric-value">{status_display}</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Steps Executed</div>
        <div class="metric-value">{steps_count}</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Elapsed Time</div>
        <div class="metric-value">{last_ts:.1f}s</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Model Spend</div>
        <div class="metric-value">${latest_cost:.4f}</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Active Run</div>
        <div class="metric-value" style="font-size: 0.95rem;">{current_run_dir.name[:18]}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Human-in-the-Loop Question Prompt Banner (if waiting for user input)
q_path = current_run_dir / "question.json"
a_path = current_run_dir / "answer.json"
if q_path.exists() and not a_path.exists():
    try:
        q_data = json.loads(q_path.read_text(encoding="utf-8"))
        st.markdown(f"""
        <div class="ask-box">
            <h4 style="margin: 0 0 8px 0; color: #fbbf24; font-size: 1.1rem;">🙋 Clarification Required:</h4>
            <div style="font-size: 1.05rem; font-weight: 500; color: #fef3c7;">{q_data.get('question', '')}</div>
        </div>
        """, unsafe_allow_html=True)

        if q_data.get("options"):
            st.markdown("**Select an option to proceed:**")
            opt_cols = st.columns(min(len(q_data["options"]), 4))
            for i, opt in enumerate(q_data["options"]):
                with opt_cols[i % len(opt_cols)]:
                    if st.button(f"👉 {opt}", key=f"qopt_{i}", use_container_width=True):
                        a_path.write_text(json.dumps({"answer": opt}), encoding="utf-8")
                        st.success(f"Selected: {opt}")
                        st.rerun()
        else:
            txt_ans = st.text_input("Type your response:", key="user_answer_input")
            if st.button("Submit Response", type="primary"):
                if txt_ans:
                    a_path.write_text(json.dumps({"answer": txt_ans}), encoding="utf-8")
                    st.success("Response submitted!")
                    st.rerun()
    except Exception:
        pass

# ==========================================
# Main Split: Activity Stream & Visual Proof
# ==========================================
col_activity, col_proof = st.columns([3, 2], gap="large")

with col_activity:
    tab_trace, tab_plan, tab_facts = st.tabs(["📋 Activity Feed", "🎯 Subgoals & Plan", "💡 Extracted Facts"])

    with tab_trace:
        if not rows:
            st.caption("Waiting for agent to initialize...")
        
        for r in rows:
            kind = r.get("kind")
            step = r.get("step", 0)

            if kind == "tool":
                tool_name = r.get("tool", "tool")
                res = r.get("result") or {}
                ok = res.get("ok", True)
                err_cls = r.get("error_class") or ""
                badge_text = "SUCCESS" if ok else f"FAILED: {err_cls}"
                icon = "⚙️" if ok else "⚠️"

                with st.expander(f"Step {step} • {tool_name} — {badge_text}", expanded=(not ok)):
                    c_arg, c_res = st.columns(2)
                    with c_arg:
                        st.markdown("**Input Parameters:**")
                        st.json(r.get("args") or {})
                    with c_res:
                        st.markdown("**Tool Output:**")
                        st.json(res)
            
            elif kind == "note":
                st.markdown(f"""
                <div class="thought-card">
                    <div class="thought-icon">🧠</div>
                    <div class="thought-text">{r.get('text', '')}</div>
                </div>
                """, unsafe_allow_html=True)
            
            elif kind == "ask":
                st.markdown(f"""
                <div class="thought-card" style="border-color: rgba(245, 158, 11, 0.4); background: rgba(245, 158, 11, 0.08);">
                    <div class="thought-icon">❓</div>
                    <div class="thought-text"><strong style="color: #fbbf24;">Asked User:</strong> {r.get('question', '')}</div>
                </div>
                """, unsafe_allow_html=True)
            
            elif kind == "answer":
                st.markdown(f"""
                <div class="thought-card" style="border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.08);">
                    <div class="thought-icon">💬</div>
                    <div class="thought-text"><strong style="color: #34d399;">User Answer:</strong> {r.get('answer', '')}</div>
                </div>
                """, unsafe_allow_html=True)

            elif kind == "verify":
                st.info(f"🔎 Verification checkpoint: {r.get('result')}")

    with tab_plan:
        plan_rows = [r for r in rows if r.get("tool") == "set_plan"]
        if plan_rows:
            latest_plan = plan_rows[-1].get("args", {})
            subgoals = latest_plan.get("subgoals", [])
            criteria = latest_plan.get("criteria", [])

            st.markdown("#### Planned Subgoals:")
            for i, sg in enumerate(subgoals):
                st.markdown(f"""
                <div class="subgoal-item">
                    <span style="color: #38bdf8; font-weight: 700; font-family: 'JetBrains Mono', monospace;">0{i+1}</span>
                    <span>{sg}</span>
                </div>
                """, unsafe_allow_html=True)

            if criteria:
                st.markdown("#### Independent Success Criteria:")
                for c in criteria:
                    st.code(f"{c.get('description', '')} ({c.get('tool', '')})")
        else:
            st.caption("Plan will appear once the agent formulates subgoals.")

    with tab_facts:
        if result_path.exists():
            rep = json.loads(result_path.read_text(encoding="utf-8"))
            facts = rep.get("facts", {})
            if facts:
                st.json(facts)
            else:
                st.caption("No structured facts recorded.")
        else:
            st.caption("Facts will be finalized upon task completion.")

with col_proof:
    st.markdown("### 🖥️ **Live Browser Viewport**")
    shots = sorted(current_run_dir.glob("shot_*.png"))
    
    # Render in Browser Window Mockup
    st.markdown("""
    <div class="browser-mockup">
        <div class="browser-chrome">
            <div class="traffic-lights">
                <span class="traffic-dot traffic-red"></span>
                <span class="traffic-dot traffic-yellow"></span>
                <span class="traffic-dot traffic-green"></span>
            </div>
            <div class="browser-url-bar">
                <span>🔒</span>
                <span>http://localhost:8001 / 8002</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if shots:
        latest_shot = shots[-1]
        st.image(
            str(latest_shot),
            caption=f"Viewport: {latest_shot.name} ({len(shots)} total captures)",
        )
        with st.expander(f"Browse all {len(shots)} captures"):
            for s in reversed(shots):
                st.image(str(s), caption=s.name)
    else:
        st.markdown("""
        <div style="border: 2px dashed #334155; border-radius: 8px; padding: 36px; text-align: center; color: #64748b; font-size: 0.9rem;">
            Screenshots from Chromium will appear here live as pages navigate.
        </div>
        """, unsafe_allow_html=True)

    # PDF / Evidence documents
    docs = sorted(p for p in current_run_dir.iterdir() if p.suffix.lower() in (".pdf", ".csv", ".txt", ".json") and not p.name in ("trace.jsonl", "result.json", "question.json", "answer.json", "cli.log"))
    if docs:
        st.markdown("#### 📁 Downloaded Evidence Artifacts:")
        for doc in docs:
            st.markdown(f"""
            <span class="evidence-badge">
                📄 <strong>{doc.name}</strong> ({doc.stat().st_size} bytes)
            </span>
            """, unsafe_allow_html=True)

# ==========================================
# Final Result & Verification Report
# ==========================================
if result_path.exists():
    try:
        rep = json.loads(result_path.read_text(encoding="utf-8"))
        st.markdown("---")
        st.markdown("## 🏁 **Task Verification Report**")

        status_type = rep.get("status", "unknown")
        passed = rep.get("verification_passed", False)
        summary_text = rep.get("summary", "")

        if status_type == "done" and passed:
            st.success(f"### ✅ **SUCCESS**: {summary_text}")
        elif status_type == "done":
            st.warning(f"### ⚠️ **COMPLETED (Verification Unconfirmed)**: {summary_text}")
        else:
            st.error(f"### 🛑 **{status_type.upper()}**: {summary_text}")

        # Verification Criteria Breakdown
        verified_items = rep.get("verified", [])
        if verified_items:
            st.markdown("#### Independent Criteria Verification:")
            for v in verified_items:
                match = v.get("match")
                if match is True:
                    v_pill = "🟢 **PASS**"
                elif match is False:
                    v_pill = "🔴 **FAIL**"
                else:
                    v_pill = "🟡 **JUDGE EVALUATED**"
                st.markdown(f"- {v_pill}: `{v.get('criterion', '')}` → *{v.get('observed', '')}*")

    except Exception as e:
        st.error(f"Error reading result.json: {e}")

elif running:
    # Auto-refresh while task is in progress
    time.sleep(1.5)
    st.rerun()
