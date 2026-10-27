"""AutoFlow_AI - Autonomous Workflow Studio
Modern, intuitive, responsive, and overflow-proof dashboard for running autonomous agents.
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
    /* Reset & Global constraints */
    *, *::before, *::after {
        box-sizing: border-box;
    }
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
        overflow-x: auto;
    }
    
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 100% !important;
    }

    /* Prevent any text or container from overflowing horizontally */
    .stAlert, .stMarkdown, div[data-testid="stExpander"], .thought-card, .metric-card {
        overflow-wrap: anywhere !important;
        word-break: break-word !important;
        max-width: 100% !important;
    }

    /* Studio Header */
    .studio-header {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.98) 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 14px;
        padding: 16px 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    }
    
    .header-top-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 12px;
    }

    .brand-group {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .brand-icon {
        width: 36px;
        height: 36px;
        border-radius: 8px;
        background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        box-shadow: 0 0 14px rgba(245, 158, 11, 0.35);
    }

    .brand-title {
        font-size: 1.45rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.02em;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .brand-title-accent {
        background: linear-gradient(90deg, #38bdf8 0%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .brand-badge {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 2px 7px;
        border-radius: 4px;
        background: rgba(56, 189, 248, 0.12);
        color: #38bdf8;
        border: 1px solid rgba(56, 189, 248, 0.3);
    }

    .header-desc {
        color: #94a3b8;
        font-size: 0.85rem;
        margin-top: 6px;
    }

    /* Services status pills */
    .services-bar {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }

    .svc-pill {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 4px 9px;
        border-radius: 9999px;
        font-size: 0.74rem;
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

    /* Native metrics card styling */
    [data-testid="stMetric"] {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 10px 14px;
        overflow: hidden;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.74rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        color: #94a3b8 !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        color: #f8fafc !important;
        font-family: 'JetBrains Mono', monospace !important;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    /* Thought Callout Card */
    .thought-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.75) 0%, rgba(49, 46, 129, 0.25) 100%);
        border: 1px solid rgba(129, 140, 248, 0.28);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 10px;
        display: flex;
        gap: 12px;
        align-items: flex-start;
        overflow-wrap: anywhere;
    }
    .thought-icon {
        font-size: 1.1rem;
        line-height: 1;
        padding-top: 2px;
        flex-shrink: 0;
    }
    .thought-text {
        font-size: 0.88rem;
        color: #e2e8f0;
        line-height: 1.45;
        overflow-wrap: anywhere;
        word-break: break-word;
    }

    /* Browser Mockup Window */
    .browser-mockup {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 10px;
        overflow: hidden;
        margin-bottom: 12px;
    }

    .browser-chrome {
        background: #1e293b;
        padding: 6px 12px;
        display: flex;
        align-items: center;
        gap: 10px;
        border-bottom: 1px solid #334155;
    }

    .traffic-lights {
        display: flex;
        gap: 5px;
    }
    .traffic-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }
    .traffic-red { background: #ef4444; }
    .traffic-yellow { background: #f59e0b; }
    .traffic-green { background: #10b981; }

    .browser-url-bar {
        flex: 1;
        background: #0f172a;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 0.72rem;
        color: #94a3b8;
        font-family: 'JetBrains Mono', monospace;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Subgoal Item */
    .subgoal-item {
        padding: 8px 12px;
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(51, 65, 85, 0.7);
        border-radius: 6px;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 0.86rem;
        color: #f1f5f9;
    }

    /* Human ask banner */
    .ask-box {
        background: linear-gradient(135deg, rgba(120, 53, 15, 0.4) 0%, rgba(69, 26, 3, 0.7) 100%);
        border: 1px solid rgba(245, 158, 11, 0.5);
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 16px;
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

    # Sample Quick-Select Tasks (Note: NO raw unescaped dollar signs to prevent LaTeX math overflow!)
    st.markdown("**1-Click Scenario Templates:**")
    demo_scenarios = {
        "🌟 Happy Path (Acme Supplies)": {
            "prompt": "Find the latest invoice from Acme Supplies and enter it in FinanceDesk.",
            "desc": "Navigates 2 pages, normalizes date format, and selects Amount Due (USD 4,250) instead of Gross Total (USD 5,000)."
        },
        "❓ Ambiguity (Globex Corp)": {
            "prompt": "Find the latest invoice from Globex Corp and enter it in FinanceDesk.",
            "desc": "Two invoices share the latest date. Agent pauses and asks for human clarification."
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
            "desc": "PDF contains prompt injection attack. Agent safely ignores it and enters the invoice."
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
        height=95,
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
            <h1 class="brand-title">AutoFlow <span class="brand-title-accent">AI</span></h1>
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

# Render Native, Responsive Streamlit Metric Cards
status_display = "🟢 Running" if running else ("🏁 Finished" if result_path.exists() else "⚪ Idle")
m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.metric("Status", status_display)
with m2:
    st.metric("Steps", steps_count)
with m3:
    st.metric("Duration", f"{last_ts:.1f}s")
with m4:
    st.metric("Cost", f"${latest_cost:.4f}")
with m5:
    st.metric("Run ID", current_run_dir.name[:18])

# Human-in-the-Loop Question Prompt Banner (if waiting for user input)
q_path = current_run_dir / "question.json"
a_path = current_run_dir / "answer.json"
if q_path.exists() and not a_path.exists():
    try:
        q_data = json.loads(q_path.read_text(encoding="utf-8"))
        st.markdown(f"""
        <div class="ask-box">
            <h4 style="margin: 0 0 6px 0; color: #fbbf24; font-size: 1.05rem;">🙋 Clarification Required:</h4>
            <div style="font-size: 1rem; font-weight: 500; color: #fef3c7;">{q_data.get('question', '')}</div>
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
col_activity, col_proof = st.columns([3, 2], gap="medium")

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
    st.markdown("### 🖥️ Live Browser")
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
            caption=f"Capture: {latest_shot.name} ({len(shots)} captures)",
        )
        with st.expander(f"Browse all {len(shots)} captures"):
            for s in reversed(shots):
                st.image(str(s), caption=s.name)
    else:
        st.markdown("""
        <div style="border: 2px dashed #334155; border-radius: 8px; padding: 32px 16px; text-align: center; color: #64748b; font-size: 0.88rem;">
            Screenshots from Chromium will appear here live as pages navigate.
        </div>
        """, unsafe_allow_html=True)

    # PDF / Evidence documents
    docs = sorted(p for p in current_run_dir.iterdir() if p.suffix.lower() in (".pdf", ".csv", ".txt", ".json") and not p.name in ("trace.jsonl", "result.json", "question.json", "answer.json", "cli.log"))
    if docs:
        st.markdown("#### 📁 Evidence Files:")
        for doc in docs:
            st.markdown(f"📄 `{doc.name}` ({doc.stat().st_size} bytes)")

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
