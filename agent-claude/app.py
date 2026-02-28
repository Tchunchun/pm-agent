"""
PM Strategy Copilot — Streamlit Web Application

Five tabs: Chat | Today | Insights | Requests | Settings
"""

import sys
from pathlib import Path

# Ensure the agent-claude directory is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from datetime import date, datetime, timezone

from config import APP_TITLE, APP_ICON, OPENAI_API_KEY, INBOX_DIR
from models import CustomerRequest, StrategicInsight
from models.workroom import WorkroomSession, CustomAgent, OUTPUT_TYPE_META
from storage import StorageManager
from agents import Orchestrator
from agents.topic_classifier import TopicClassifier
from agents.facilitator_agent import FacilitatorAgent
from agents.agent_designer import AgentDesigner
from skills.bootstrap import bootstrap_skills


# ------------------------------------------------------------------ #
# Agent registry — used by Chat tab selector                         #
# ------------------------------------------------------------------ #

AGENT_REGISTRY = [
    # Tier 1
    {"key": "intake",     "label": "Intake",      "emoji": "📥", "tier": 1,
     "description": "Log requests · Process files · Document Q&A", "mode": "work"},
    {"key": "planner",    "label": "Planner",     "emoji": "📅", "tier": 1,
     "description": "Plan your day · Synthesise priorities", "mode": "work"},
    {"key": "analyst",    "label": "Analyst",     "emoji": "📊", "tier": 1,
     "description": "Trends · Gaps · Risks · Decisions", "mode": "work"},
    # Tier 2
    {"key": "challenger", "label": "Challenger",  "emoji": "⚔️",  "tier": 2,
     "description": "Red-team ideas · Argue the opposing view", "mode": "work"},
    {"key": "writer",     "label": "Writer",      "emoji": "✍️",  "tier": 2,
     "description": "Draft emails · Teams messages · Exec briefs", "mode": "work"},
    {"key": "researcher", "label": "Researcher",  "emoji": "🔍", "tier": 2,
     "description": "Deep dives · Industry context · Customer background", "mode": "work"},
]

TIER1_DEFAULTS = ["intake", "planner", "analyst"]


# ------------------------------------------------------------------ #
# Page config                                                         #
# ------------------------------------------------------------------ #

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ------------------------------------------------------------------ #
# Session state init                                                  #
# ------------------------------------------------------------------ #

def _init_state():
    if "storage" not in st.session_state:
        st.session_state.storage = StorageManager()
        # Bootstrap skills once, after storage is ready
        bootstrap_skills(storage=st.session_state.storage)
    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = Orchestrator(st.session_state.storage)
    if "messages" not in st.session_state:
        st.session_state.messages = st.session_state.storage.load_conversation()
    if "nav_page" not in st.session_state:
        st.session_state.nav_page = "chat"
    if "processed_file_keys" not in st.session_state:
        st.session_state.processed_file_keys = set()
    if "active_document" not in st.session_state:
        st.session_state.active_document = None
    if "active_agents" not in st.session_state:
        st.session_state.active_agents = list(TIER1_DEFAULTS)
    # ---- Workroom state ----
    if "workroom_id" not in st.session_state:
        st.session_state.workroom_id = None
    if "workroom_messages" not in st.session_state:
        st.session_state.workroom_messages = []
    if "show_new_workroom_form" not in st.session_state:
        st.session_state.show_new_workroom_form = False
    if "show_custom_agent_form" not in st.session_state:
        st.session_state.show_custom_agent_form = False
    if "show_explore_form" not in st.session_state:
        st.session_state.show_explore_form = False
    if "explore_results" not in st.session_state:
        st.session_state.explore_results = None   # dict: {reasoning, agents} or None
    if "explore_selected" not in st.session_state:
        st.session_state.explore_selected = {}    # {agent_key: bool}
    if "show_output_panel" not in st.session_state:
        st.session_state.show_output_panel = False
    if "workroom_file_keys" not in st.session_state:
        st.session_state.workroom_file_keys = set()
    if "workroom_active_document" not in st.session_state:
        st.session_state.workroom_active_document = None
    if "editing_agent_id" not in st.session_state:
        st.session_state.editing_agent_id = None
    if "new_workroom_pending_doc" not in st.session_state:
        st.session_state.new_workroom_pending_doc = None
    if "new_workroom_file_key" not in st.session_state:
        st.session_state.new_workroom_file_key = None
    # ---- Create-workroom form state ----
    if "wr_create_mode" not in st.session_state:
        st.session_state.wr_create_mode = "work"
    if "wr_create_agents" not in st.session_state:
        st.session_state.wr_create_agents = list(TIER1_DEFAULTS)
    if "wr_create_file_bytes" not in st.session_state:
        st.session_state.wr_create_file_bytes = None
    if "wr_create_file_name" not in st.session_state:
        st.session_state.wr_create_file_name = None
    # ---- New workroom wizard state ----
    if "wr_wizard_step" not in st.session_state:
        st.session_state.wr_wizard_step = 0          # 0=hidden, 1=goal, 2=agents, 3=create
    if "wr_wizard_topic" not in st.session_state:
        st.session_state.wr_wizard_topic = ""
    if "wr_wizard_context" not in st.session_state:
        st.session_state.wr_wizard_context = ""    # raw freeform user input
    if "wr_wizard_objective" not in st.session_state:
        st.session_state.wr_wizard_objective = ""   # parsed by LLM
    if "wr_wizard_outcome" not in st.session_state:
        st.session_state.wr_wizard_outcome = ""      # parsed by LLM
    if "wr_wizard_file_bytes" not in st.session_state:
        st.session_state.wr_wizard_file_bytes = None
    if "wr_wizard_file_name" not in st.session_state:
        st.session_state.wr_wizard_file_name = None
    if "wr_wizard_recommended" not in st.session_state:
        st.session_state.wr_wizard_recommended = []
    if "wr_wizard_rationale" not in st.session_state:
        st.session_state.wr_wizard_rationale = {}
    if "wr_wizard_final_agents" not in st.session_state:
        st.session_state.wr_wizard_final_agents = []
    # Seed default agents on first run (no-op if already present)
    st.session_state.storage.ensure_default_agents()


_init_state()

storage: StorageManager = st.session_state.storage
orchestrator: Orchestrator = st.session_state.orchestrator

today_str = date.today().isoformat()
today_display = date.today().strftime("%a %d %b")


# ------------------------------------------------------------------ #
# Design System CSS — see docs/UI_UX_DESIGN_GUIDELINE.md              #
# Typography reference: Claude Code (Anthropic)                       #
# Root: 13 px · Font: Inter + JetBrains Mono · 4 px grid spacing     #
# ------------------------------------------------------------------ #

_css_path = Path(__file__).parent / "static" / "style.css"
_css_text = _css_path.read_text()
st.markdown(f"<style>{_css_text}</style>", unsafe_allow_html=True)


# ------------------------------------------------------------------ #
# Helper functions                                                    #
# ------------------------------------------------------------------ #

def _agent_label_map() -> dict[str, str]:
    """Return {key: 'emoji Label'} for all built-in + custom agents."""
    m = {a["key"]: f"{a['emoji']} {a['label']}" for a in AGENT_REGISTRY}
    for ca in storage.list_custom_agents():
        m[ca.key] = f"{ca.emoji} {ca.label}"
    return m


def _all_agent_options() -> list[dict]:
    """Return all agent option dicts (built-in + custom), sorted by category."""
    opts = list(AGENT_REGISTRY)
    for ca in storage.list_custom_agents():
        opts.append({
            "key": ca.key,
            "label": ca.label,
            "emoji": ca.emoji,
            "tier": 3,
            "category": ca.category,         # "professional", "life", or ""
            "is_default": ca.is_default,
            "description": ca.description or ca.system_prompt[:80],
        })
    return opts


def _agent_display_label(agent_dict: dict) -> str:
    """Return a display label for an agent option, with category prefix."""
    emoji = agent_dict.get("emoji", "🤖")
    label = agent_dict.get("label", agent_dict["key"])
    category = agent_dict.get("category", "")
    tier = agent_dict.get("tier", 3)
    if tier in (1, 2):
        return f"{emoji} {label}"
    elif category == "professional":
        return f"{emoji} {label} · Professional"
    elif category == "life":
        return f"{emoji} {label} · Life"
    else:
        return f"{emoji} {label}"


def _parse_meeting_context(raw_context: str, topic: str) -> dict:
    """
    Use OpenAI to extract a structured meeting objective and desired outcome
    from freeform user context. Returns {"objective": str, "outcome": str}.
    """
    from config import MODEL, make_openai_client
    import json as _json

    client = make_openai_client()
    prompt = f"""You are a TPM assistant. The user wants to set up a meeting workroom.

Topic: {topic}

User's context (freeform):
\"\"\" 
{raw_context}
\"\"\"

Extract exactly two things from the context above:
1. **Meeting objective** — what they want to discuss, decide, or accomplish in this session (1–3 sentences).
2. **Desired outcome** — the concrete deliverable(s) or result(s) they expect to walk away with (1–2 sentences).

Return ONLY valid JSON, no markdown fences:
{{"objective": "...", "outcome": "..."}}"""

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            max_tokens=400,
            temperature=0.2,
            messages=[
                {"role": "system", "content": "You extract structured meeting metadata from freeform text. Return only JSON."},
                {"role": "user", "content": prompt},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        parsed = _json.loads(raw)
        return {
            "objective": parsed.get("objective", raw_context[:300]),
            "outcome": parsed.get("outcome", ""),
        }
    except Exception:
        # Fallback: use first half as objective, second half as outcome
        mid = len(raw_context) // 2
        return {
            "objective": raw_context[:mid].strip() or raw_context,
            "outcome": raw_context[mid:].strip(),
        }


def _save_workroom_messages(workroom_id: str, msgs: list[dict]) -> None:
    storage.save_workroom_messages(workroom_id, msgs)


def _load_workroom_messages(workroom_id: str) -> list[dict]:
    return storage.load_workroom_messages(workroom_id)


# ------------------------------------------------------------------ #
# Sidebar — Navigation                                                #
# ------------------------------------------------------------------ #

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")

    st.divider()

    # Preload workrooms for sidebar
    _sb_wrs = storage.list_workrooms(include_archived=False)

    # API key check
    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY not set.\nSet it in your environment or .env file.")
        st.stop()

    # ============================================================ #
    # 💬 Chat Room                                                  #
    # ============================================================ #
    st.markdown("**💬 Chat Room**")

    if st.button("✨  New Workroom", key="nav_new_wr", use_container_width=True):
        st.session_state.nav_page = "chat"
        st.session_state.show_new_workroom_form = True
        st.session_state.workroom_id = None
        st.session_state.workroom_messages = []
        st.session_state.new_workroom_pending_doc = None
        st.session_state.new_workroom_file_key = None
        # Reset wizard state
        st.session_state.wr_wizard_step = 1
        st.session_state.wr_wizard_topic = ""
        st.session_state.wr_wizard_context = ""
        st.session_state.wr_wizard_objective = ""
        st.session_state.wr_wizard_outcome = ""
        st.session_state.wr_wizard_file_bytes = None
        st.session_state.wr_wizard_file_name = None
        st.session_state.wr_wizard_recommended = []
        st.session_state.wr_wizard_rationale = {}
        st.session_state.wr_wizard_final_agents = []
        st.rerun()

    # Existing Workroom
    _is_existing = st.session_state.nav_page == "chat" and not st.session_state.workroom_id and not st.session_state.show_new_workroom_form
    _ew_type = "primary" if _is_existing else "secondary"
    if st.button("💬  Existing Workroom", key="nav_existing_wr", use_container_width=True, type=_ew_type):
        st.session_state.nav_page = "chat"
        st.session_state.workroom_id = None
        st.session_state.show_new_workroom_form = False
        st.rerun()

    st.divider()

    # ============================================================ #
    # ⚙️ Settings                                                   #
    # ============================================================ #
    st.markdown("**⚙️ Settings**")
    _nav_hub_type = "primary" if st.session_state.nav_page == "agent_hub" else "secondary"
    if st.button("🤖  Agent Hub", key="nav_agent_hub", use_container_width=True, type=_nav_hub_type):
        st.session_state.nav_page = "agent_hub"
        st.rerun()

    st.divider()

    # ============================================================ #
    # Preview                                                       #
    # ============================================================ #
    st.markdown("**Preview**")
    st.caption("Coming soon — these features are in early preview.")

    _nav_today_type = "primary" if st.session_state.nav_page == "today" else "secondary"
    if st.button("📅  Today", key="nav_today", use_container_width=True, type=_nav_today_type):
        st.session_state.nav_page = "today"
        st.rerun()

    _nav_ins_type = "primary" if st.session_state.nav_page == "insights" else "secondary"
    if st.button("💡  Insights", key="nav_insights", use_container_width=True, type=_nav_ins_type):
        st.session_state.nav_page = "insights"
        st.rerun()

    _nav_req_type = "primary" if st.session_state.nav_page == "requests" else "secondary"
    if st.button("📋  Requests", key="nav_requests", use_container_width=True, type=_nav_req_type):
        st.session_state.nav_page = "requests"
        st.rerun()

    st.divider()
    st.caption("All data stays local.\nOnly inference is sent to the API.")


# ------------------------------------------------------------------ #
# Page routing variable                                               #
# ------------------------------------------------------------------ #

page = st.session_state.nav_page


# ================================================================== #
# PAGE: TODAY                                                         #
# ================================================================== #

if page == "today":
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"## Today — {today_display}")
    with col2:
        if st.button("🔄 Refresh plan", key="refresh_plan"):
            st.rerun()

    # Upload briefing
    with st.expander("📥 Upload today's briefing file", expanded=not bool(storage.get_day_plan(today_str))):
        uploaded = st.file_uploader(
            "Paste or upload your Microsoft Copilot briefing",
            type=["md", "txt"],
            key="briefing_upload",
        )
        col_paste, col_help = st.columns([3, 1])
        with col_paste:
            pasted_briefing = st.text_area(
                "Or paste briefing text here",
                height=120,
                placeholder="# Daily PM Briefing — 2026-02-26\n\n## Today's Meetings\n...",
                key="pasted_briefing",
            )
        with col_help:
            st.info("Get your briefing from Microsoft Copilot each morning.")

        if st.button("▶ Run morning workflow", key="run_morning", type="primary"):
            if uploaded or pasted_briefing.strip():
                with st.spinner("[Intake] Parsing briefing..."):
                    if uploaded:
                        file_bytes = uploaded.read()
                        filename = uploaded.name
                    else:
                        file_bytes = pasted_briefing.encode("utf-8")
                        filename = f"briefing_{today_str}.md"

                    response = orchestrator.handle_message(
                        "start my day",
                        file_bytes=file_bytes,
                        filename=filename,
                        date=today_str,
                    )

                    if response.get("pending_action") == "confirm_briefing_mentions":
                        st.session_state["pending_morning_response"] = response
                        st.rerun()
                    else:
                        st.success(response["text"])
                        st.rerun()
            else:
                st.warning("Please upload a file or paste your briefing text.")

    # Handle pending mention confirmation
    if "pending_morning_response" in st.session_state:
        presponse = st.session_state["pending_morning_response"]
        st.info(presponse["text"])
        col_log, col_skip = st.columns(2)
        with col_log:
            if st.button("✅ Log all customer mentions", key="log_mentions"):
                with st.spinner("[Intake] Logging requests..."):
                    final_response = orchestrator.handle_message("log all")
                    del st.session_state["pending_morning_response"]
                    st.success(final_response["text"])
                    st.rerun()
        with col_skip:
            if st.button("⏭ Skip", key="skip_mentions"):
                with st.spinner("[Planner] Building your plan..."):
                    final_response = orchestrator.handle_message("skip")
                    del st.session_state["pending_morning_response"]
                    st.success(final_response["text"])
                    st.rerun()

    # Current day plan
    today_plan = storage.get_day_plan(today_str)

    if today_plan:
        st.divider()

        # Stats row with card styling
        meta_col1, meta_col2, meta_col3 = st.columns(3)
        with meta_col1:
            total = len(today_plan.focus_items)
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-value">{total}</div>'
                f'<div class="stat-label">Focus Items</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with meta_col2:
            done = sum(1 for i in today_plan.focus_items if i.done)
            pct = int(done / total * 100) if total else 0
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-value">{done}/{total}</div>'
                f'<div class="stat-label">Completed ({pct}%)</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with meta_col3:
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-value" style="font-size:0.9rem;">{today_plan.briefing_source}</div>'
                f'<div class="stat-label">Source</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # Focus items
        for item in sorted(today_plan.focus_items, key=lambda x: x.rank):
            with st.container():
                check_col, content_col = st.columns([0.05, 0.95])
                with check_col:
                    done_val = st.checkbox(
                        "Done",
                        value=item.done,
                        key=f"item_done_{item.rank}_{today_plan.id}",
                        label_visibility="collapsed",
                    )
                    if done_val != item.done:
                        storage.update_focus_item_done(today_str, item.rank, done_val)
                        st.rerun()
                with content_col:
                    item_class = "focus-done" if item.done else ""
                    priority_badges = ""
                    for rid in item.linked_request_ids[:2]:
                        req = storage.get_request(rid)
                        if req:
                            priority_badges += f' <span class="badge-{req.priority}">{req.priority}</span>'
                    st.markdown(
                        f'<div class="{item_class}">'
                        f'<strong>{item.rank}. {item.title}</strong>{priority_badges}'
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"Why: {item.why}")
                    if item.linked_request_ids:
                        refs = " · ".join(f"#{rid}" for rid in item.linked_request_ids)
                        st.caption(f"Source: {item.source_type} · {refs} | ~{item.estimated_minutes} min")
                    else:
                        st.caption(f"Source: {item.source_type} · {item.source_ref} | ~{item.estimated_minutes} min")

        # Meetings
        if today_plan.meetings_today:
            st.divider()
            st.markdown("**Today's meetings**")
            for meeting in today_plan.meetings_today:
                st.markdown(
                    f'<div class="meeting-strip">🕐 {meeting.get("start_time", "?")}  '
                    f'<strong>{meeting.get("title", "Meeting")}</strong>  '
                    f'({meeting.get("duration_min", "?")} min)</div>',
                    unsafe_allow_html=True,
                )
    else:
        if "pending_morning_response" not in st.session_state:
            st.markdown(
                '<div class="empty-state">'
                '<div class="empty-state-icon">📅</div>'
                '<div class="empty-state-text">No plan for today yet.<br>Upload your briefing above to get started.</div>'
                '</div>',
                unsafe_allow_html=True,
            )

    # History
    st.divider()
    with st.expander("📆 Plan history"):
        past_plans = storage.list_day_plans(limit=7)
        past_plans = [p for p in past_plans if p.date != today_str]
        if not past_plans:
            st.caption("No past plans yet.")
        for plan in past_plans:
            done = sum(1 for i in plan.focus_items if i.done)
            total = len(plan.focus_items)
            date_obj = datetime.strptime(plan.date, "%Y-%m-%d")
            date_label = date_obj.strftime("%a %d %b")
            with st.expander(f"{date_label} — {done}/{total} done"):
                for item in sorted(plan.focus_items, key=lambda x: x.rank):
                    icon = "✅" if item.done else "⬜"
                    st.markdown(f"{icon} **{item.rank}. {item.title}**  \n_{item.why}_")


# ================================================================== #
# PAGE: CHAT ROOM                                                     #
# ================================================================== #

if page == "chat":

    # ================================================================
    # Chat Area (active workroom or existing workroom)
    # ================================================================
    with st.container():

        active_ws: WorkroomSession | None = None
        if st.session_state.workroom_id:
            active_ws = storage.get_workroom(st.session_state.workroom_id)
            if active_ws is None:
                st.session_state.workroom_id = None

        # ================================================================
        # MODE C: New Workroom Creation Wizard (3-step)
        # ================================================================
        if st.session_state.show_new_workroom_form and not active_ws:
            wizard_step = st.session_state.wr_wizard_step or 1

            # ---- Progress indicator ----
            step_labels = ["Goal & Context", "Agent Recommendation", "Launch"]
            pcol1, pcol2, pcol3 = st.columns(3)
            for i, (col, lbl) in enumerate(zip([pcol1, pcol2, pcol3], step_labels), 1):
                with col:
                    if i < wizard_step:
                        st.markdown(f"~~**Step {i}:** {lbl}~~ ✅")
                    elif i == wizard_step:
                        st.markdown(f"**Step {i}:** {lbl} ◀")
                    else:
                        st.markdown(f"Step {i}: {lbl}")
            st.divider()

            # ============================================================
            # STEP 1: Goal Setting — Topic, Objective, Outcome, Docs
            # ============================================================
            if wizard_step == 1:
                st.markdown("### 🎯 Step 1 — Define Your Meeting Goal")
                st.caption("What do you want to discuss, and what outcome do you expect?")

                wr_topic = st.text_input(
                    "Topic *",
                    value=st.session_state.wr_wizard_topic,
                    placeholder="e.g., AI Assistant Feature — MVP Scoping",
                    key="nw_topic",
                )
                wr_context = st.text_area(
                    "Context *",
                    value=st.session_state.wr_wizard_context,
                    height=180,
                    placeholder=(
                        "Describe everything the agents need to know:\n\n"
                        "• What do you want to discuss or decide?\n"
                        "• Any background, constraints, or meeting notes?\n"
                        "• What deliverables / output do you expect?\n\n"
                        "Example: Customer shared business requirements for Denial Intelligence. "
                        "Need to define model requirements and prepare follow-up questions. "
                        "Expected output: draft model requirement doc + list of clarification questions."
                    ),
                    key="nw_context",
                    help="Just describe what you want in plain language. "
                         "The system will extract the meeting objective and desired outcome automatically.",
                )

                _opt_col1, _opt_col2 = st.columns(2)
                with _opt_col1:
                    wr_mode = st.selectbox(
                        "Mode",
                        ["work", "life"],
                        format_func=lambda x: "💼 Work" if x == "work" else "🎉 Life",
                        key="nw_mode",
                    )
                with _opt_col2:
                    wr_output = st.selectbox(
                        "Target output format",
                        list(OUTPUT_TYPE_META.keys()),
                        format_func=lambda k: f"{OUTPUT_TYPE_META[k]['emoji']} {OUTPUT_TYPE_META[k]['label']}",
                        key="nw_output",
                    )
                    selected_meta = OUTPUT_TYPE_META.get(wr_output, {})
                    if selected_meta.get("description"):
                        st.caption(selected_meta["description"])

                # ---- Supporting documents ----
                st.markdown("**📎 Supporting Documents** (optional)")
                st.caption("Upload a document to give agents context — PDF, Word, CSV, or plain text.")

                nw_file = st.file_uploader(
                    "Upload a material",
                    type=["pdf", "docx", "csv", "txt", "md"],
                    key="nw_file_upload",
                    label_visibility="collapsed",
                )
                if nw_file is not None:
                    fkey = f"{nw_file.name}_{nw_file.size}"
                    if fkey != st.session_state.new_workroom_file_key:
                        st.session_state.new_workroom_file_key = fkey
                        from utils.file_parser import extract_text_from_file
                        fbytes = nw_file.read()
                        with st.spinner(f"Reading {nw_file.name}…"):
                            doc_text = extract_text_from_file(fbytes, nw_file.name)
                        st.session_state.new_workroom_pending_doc = {
                            "filename": nw_file.name,
                            "text": doc_text[:40000],
                        }

                if st.session_state.new_workroom_pending_doc:
                    pdoc = st.session_state.new_workroom_pending_doc
                    st.success(f"📄 **{pdoc['filename']}** ready ({len(pdoc['text']):,} chars)")

                st.divider()

                # ---- Actions ----
                btn_col1, btn_col2 = st.columns([1, 4])
                with btn_col1:
                    if st.button("Cancel", key="nw_cancel"):
                        st.session_state.show_new_workroom_form = False
                        st.session_state.wr_wizard_step = 0
                        st.session_state.new_workroom_pending_doc = None
                        st.session_state.new_workroom_file_key = None
                        st.rerun()
                with btn_col2:
                    if st.button("Next → Recommend Agents", key="nw_next_step1", type="primary"):
                        if wr_topic.strip() and wr_context.strip():
                            # Save raw inputs
                            st.session_state.wr_wizard_topic = wr_topic.strip()
                            st.session_state.wr_wizard_context = wr_context.strip()

                            # Parse context into objective + outcome using LLM
                            with st.spinner("🧠 Understanding your context…"):
                                parsed = _parse_meeting_context(wr_context.strip(), wr_topic.strip())
                            st.session_state.wr_wizard_objective = parsed["objective"]
                            st.session_state.wr_wizard_outcome = parsed["outcome"]

                            # Run topic classifier
                            all_agent_opts = _all_agent_options()
                            classifier = TopicClassifier()
                            with st.spinner("🤖 Recommending agents…"):
                                result = classifier.classify(
                                    topic=wr_topic.strip(),
                                    objective=parsed["objective"],
                                    outcome=parsed["outcome"],
                                    available_agents=all_agent_opts,
                                )
                            st.session_state.wr_wizard_recommended = result.get("recommended", [])
                            st.session_state.wr_wizard_rationale = result.get("rationale", {})
                            st.session_state.wr_wizard_final_agents = list(result.get("recommended", []))
                            st.session_state.wr_wizard_step = 2
                            st.rerun()
                        else:
                            st.error("Topic and context are required.")

            # ============================================================
            # STEP 2: Agent Recommendation — review and adjust
            # ============================================================
            elif wizard_step == 2:
                st.markdown("### 🤖 Step 2 — Review Recommended Agents")
                st.caption("Based on your topic and objectives, the system recommends these agents. Adjust as needed.")

                recommended = st.session_state.wr_wizard_recommended
                rationale = st.session_state.wr_wizard_rationale
                all_agent_opts = _all_agent_options()

                # Show summary of what was entered
                with st.expander("📋 Your Meeting Brief", expanded=False):
                    st.markdown(f"**Topic:** {st.session_state.wr_wizard_topic}")
                    st.markdown(f"**Objective:** {st.session_state.wr_wizard_objective}")
                    st.markdown(f"**Desired Outcome:** {st.session_state.wr_wizard_outcome}")
                    if st.session_state.new_workroom_pending_doc:
                        st.markdown(f"**Document:** 📄 {st.session_state.new_workroom_pending_doc['filename']}")

                # Show recommended agents with rationale
                if recommended:
                    st.markdown("**✅ Recommended agents:**")
                    for agent_key in recommended:
                        agent_info = next((a for a in all_agent_opts if a["key"] == agent_key), None)
                        if agent_info:
                            emoji = agent_info.get("emoji", "🤖")
                            label = agent_info.get("label", agent_key)
                            reason = rationale.get(agent_key, "")
                            st.markdown(f"- {emoji} **{label}** — {reason}")
                else:
                    st.warning("No specific recommendations — using default agents.")

                st.markdown("---")

                # Sort agents for multiselect
                def _sort_key(a):
                    tier = a.get("tier", 3)
                    cat = a.get("category", "")
                    if tier == 1: return (0, a["label"])
                    if tier == 2: return (1, a["label"])
                    if cat == "professional": return (2, a["label"])
                    if cat == "life": return (3, a["label"])
                    return (4, a["label"])

                all_agent_opts_sorted = sorted(all_agent_opts, key=_sort_key)
                all_agent_keys = [a["key"] for a in all_agent_opts_sorted]

                # Default selection = what AI recommended (or tier 1 fallback)
                default_selection = st.session_state.wr_wizard_final_agents
                if not default_selection:
                    default_selection = [a["key"] for a in all_agent_opts_sorted if a.get("tier") == 1]

                # Filter defaults to only valid keys
                valid_defaults = [k for k in default_selection if k in all_agent_keys]

                st.markdown("**Adjust your agent team:**")
                final_agents = st.multiselect(
                    "Agents for this session",
                    all_agent_keys,
                    default=valid_defaults,
                    format_func=lambda k: next(
                        (_agent_display_label(a) for a in all_agent_opts_sorted if a["key"] == k), k
                    ),
                    key="nw_wizard_agents",
                    label_visibility="collapsed",
                )

                st.divider()

                # ---- Actions ----
                btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 3])
                with btn_col1:
                    if st.button("← Back", key="nw_back_step2"):
                        st.session_state.wr_wizard_step = 1
                        st.rerun()
                with btn_col2:
                    if st.button("Cancel", key="nw_cancel_step2"):
                        st.session_state.show_new_workroom_form = False
                        st.session_state.wr_wizard_step = 0
                        st.session_state.new_workroom_pending_doc = None
                        st.session_state.new_workroom_file_key = None
                        st.rerun()
                with btn_col3:
                    if st.button("✨ Start Session", key="nw_create_step2", type="primary"):
                        if final_agents:
                            st.session_state.wr_wizard_final_agents = final_agents

                            # Build the workroom session
                            wr_mode = st.session_state.get("nw_mode", "work")
                            wr_output = st.session_state.get("nw_output", "summary")
                            full_goal = st.session_state.wr_wizard_objective
                            desired = st.session_state.wr_wizard_outcome
                            if desired:
                                full_goal = f"{full_goal}\n\nDesired outcome: {desired}"

                            new_ws = WorkroomSession(
                                title=st.session_state.wr_wizard_topic,
                                goal=full_goal,
                                key_outcome=desired,
                                mode=wr_mode,
                                output_type=wr_output,
                                active_agents=final_agents,
                                topic_description=st.session_state.wr_wizard_topic,
                                ai_recommended_agents=st.session_state.wr_wizard_recommended,
                                facilitator_enabled=True,
                                facilitator_intro_sent=True,
                            )
                            storage.save_workroom(new_ws)

                            # Prepare messages list
                            init_msgs = []

                            # If a document was uploaded, add it as context
                            if st.session_state.new_workroom_pending_doc:
                                st.session_state.workroom_active_document = st.session_state.new_workroom_pending_doc
                                # Persist document context to workroom for cross-session access
                                new_ws.document_context = st.session_state.new_workroom_pending_doc
                                storage.save_workroom(new_ws)
                                fname = st.session_state.new_workroom_pending_doc["filename"]
                                init_msgs.append({
                                    "role": "user",
                                    "content": f"📎 Material uploaded: **{fname}**\n\nThis document is available as context for our discussion.",
                                })
                            else:
                                st.session_state.workroom_active_document = None

                            # Generate facilitator opening message
                            facilitator = FacilitatorAgent()
                            agent_details = []
                            for ak in final_agents:
                                ainfo = next((a for a in _all_agent_options() if a["key"] == ak), None)
                                if ainfo:
                                    agent_details.append(ainfo)
                            with st.spinner("🎙️ Facilitator is opening the session…"):
                                opening_msg = facilitator.open_session(new_ws, agent_details)
                            init_msgs.append({
                                "role": "assistant",
                                "content": opening_msg,
                                "agent": "🎙️ Facilitator",
                            })

                            # Save and enter the workroom
                            _save_workroom_messages(new_ws.id, init_msgs)
                            st.session_state.workroom_id = new_ws.id
                            st.session_state.workroom_messages = init_msgs
                            st.session_state.show_new_workroom_form = False
                            st.session_state.workroom_file_keys = set()
                            st.session_state.new_workroom_pending_doc = None
                            st.session_state.new_workroom_file_key = None
                            st.session_state.wr_wizard_step = 0
                            st.rerun()
                        else:
                            st.error("Please select at least one agent.")

        # ================================================================
        # MODE A: Active Workroom
        # ================================================================
        elif active_ws:
            if not st.session_state.workroom_messages:
                st.session_state.workroom_messages = _load_workroom_messages(active_ws.id)

            # Auto-restore persisted document context when entering a workroom
            if active_ws.document_context and not st.session_state.workroom_active_document:
                st.session_state.workroom_active_document = active_ws.document_context

            wmsgs = st.session_state.workroom_messages

            # ---- Layout: Immersive chat (left) + controls (right) ----
            meta = OUTPUT_TYPE_META.get(active_ws.output_type, {})
            mode_icon = "💼" if active_ws.mode == "work" else "🎉"

            wr_input = None
            _chat_col, _panel_col = st.columns([3, 1])

            with _chat_col:
                # Slim session title
                st.markdown(f"#### {mode_icon} {active_ws.title}")

                # ---- Chat messages (immersive, tall container) ----
                chat_box = st.container(height=700)
                with chat_box:
                    if not wmsgs:
                        st.markdown(
                            '<div class="empty-state">'
                            '<div class="empty-state-icon">💬</div>'
                            '<div class="empty-state-text">No messages yet.<br>Start the discussion below or upload a document for context.</div>'
                            '</div>',
                            unsafe_allow_html=True,
                        )
                    for msg in wmsgs:
                        role = msg.get("role", "user")
                        content = msg.get("content", "")
                        agent_label = msg.get("agent", "")
                        is_multi = msg.get("multi_response") is not None

                        if role == "user":
                            with st.chat_message("user"):
                                st.markdown(content)
                        elif is_multi:
                            for resp in msg.get("multi_response", []):
                                with st.chat_message("assistant"):
                                    agent_name = resp.get("agent", "")
                                    if agent_name:
                                        st.markdown(f'<div class="agent-avatar">{agent_name}</div>', unsafe_allow_html=True)
                                    st.markdown(resp.get("text", ""))
                        else:
                            with st.chat_message("assistant"):
                                if agent_label:
                                    st.markdown(f'<div class="agent-avatar">{agent_label}</div>', unsafe_allow_html=True)
                                st.markdown(content)

                # ---- Agent selector row (inside chat column, right below messages) ----
                _agent_btns = active_ws.active_agents[:8]
                _num_cols = min(len(_agent_btns) + 1, 9)  # +1 for label
                _ag_cols = st.columns(_num_cols)
                with _ag_cols[0]:
                    st.caption("**Ask:**")
                for _ai, _ak in enumerate(_agent_btns):
                    _a_info = next((a for a in _all_agent_options() if a["key"] == _ak), None)
                    _btn_label = f"{_a_info.get('emoji', '🤖')} {_a_info['label']}" if _a_info else f"🤖 {_ak}"
                    with _ag_cols[_ai + 1]:
                        if st.button(_btn_label, key=f"mention_{_ak}", use_container_width=True):
                            st.session_state["wr_mention_prefix"] = f"@{_ak} "
                            st.rerun()

            # ---- Right panel: Controls + references ----
            with _panel_col:
                # ---- 🎯 Session context (always visible) ----
                st.markdown("#### 📌 Context")
                st.markdown(f"**🎯 {active_ws.goal}**")
                st.caption(f"{meta.get('emoji', '')} {meta.get('label', '')}  ·  {'💼 Work' if active_ws.mode == 'work' else '🎉 Life'}")
                if getattr(active_ws, "key_outcome", ""):
                    st.caption(f"🏁 {active_ws.key_outcome}")

                # ---- Active document context ----
                if st.session_state.workroom_active_document:
                    doc_name = st.session_state.workroom_active_document.get("filename", "document")
                    st.info(f"📄 **{doc_name}**")
                    if st.button("✕ Remove doc", key="clear_wr_doc", use_container_width=True):
                        st.session_state.workroom_active_document = None
                        st.rerun()

                # ---- 🤖 Agent Team & Mode ----
                with st.expander("🤖 Team & Mode", expanded=False):
                    all_opts = _all_agent_options()
                    all_keys = [a["key"] for a in all_opts]
                    selected_keys = st.multiselect(
                        "Agent team",
                        all_keys,
                        default=[k for k in active_ws.active_agents if k in all_keys],
                        format_func=lambda k: next(
                            (f"{a['emoji']} {a['label']}" for a in all_opts if a["key"] == k), k
                        ),
                        key="ws_agent_team",
                    )
                    if selected_keys != active_ws.active_agents:
                        active_ws.active_agents = selected_keys
                        storage.save_workroom(active_ws)

                    disc_mode = st.radio(
                        "Discussion mode",
                        ["open", "round_table", "focused"],
                        index=["open", "round_table", "focused"].index(active_ws.discussion_mode),
                        format_func=lambda m: {
                            "open": "💬 Open",
                            "round_table": "🔄 Round Table",
                            "focused": "🎯 Focused",
                        }[m],
                        key="ws_disc_mode",
                    )
                    if disc_mode != active_ws.discussion_mode:
                        active_ws.discussion_mode = disc_mode
                        if disc_mode != "focused":
                            active_ws.focused_agent = None
                        storage.save_workroom(active_ws)

                    if disc_mode == "focused":
                        focus_opts = [a["key"] for a in all_opts]
                        current_focused = active_ws.focused_agent or (focus_opts[0] if focus_opts else None)
                        focused_agent = st.selectbox(
                            "Focused agent",
                            focus_opts,
                            index=focus_opts.index(current_focused) if current_focused in focus_opts else 0,
                            format_func=lambda k: next(
                                (f"{a['emoji']} {a['label']}" for a in all_opts if a["key"] == k), k
                            ),
                            key="ws_focused_agent",
                        )
                        if focused_agent != active_ws.focused_agent:
                            active_ws.focused_agent = focused_agent
                            storage.save_workroom(active_ws)

                # Active agents + mode caption
                agent_map = _agent_label_map()
                active_labels = " · ".join(agent_map.get(k, k) for k in active_ws.active_agents)
                disc_label = {"open": "💬 Open", "round_table": "🔄 Round Table", "focused": "🎯 Focused"}.get(active_ws.discussion_mode, "")
                st.caption(f"**Team:** {active_labels}  |  **Mode:** {disc_label}")

                # ---- ⚡ Actions (no expander — always visible) ----
                if st.button(
                    "🔄 Round Table",
                    key="btn_round_table",
                    help="Ask every active agent to respond",
                    use_container_width=True,
                    disabled=not wmsgs or active_ws.discussion_mode != "round_table",
                ):
                    last_user_msg = next(
                        (m["content"] for m in reversed(wmsgs) if m.get("role") == "user"), ""
                    )
                    if last_user_msg:
                        with st.spinner("All agents thinking…"):
                            result = orchestrator.round_table(
                                last_user_msg,
                                active_agents=active_ws.active_agents,
                                conversation_history=wmsgs,
                                document_context=st.session_state.workroom_active_document,
                                workroom=active_ws,
                            )
                        wmsgs.append({
                            "role": "assistant",
                            "content": result["text"],
                            "agent": "[Round Table]",
                            "multi_response": result.get("multi_response"),
                        })
                        _save_workroom_messages(active_ws.id, wmsgs)
                        st.session_state.workroom_messages = wmsgs
                        st.rerun()

                if st.button(
                    f"{meta.get('emoji', '📄')} Generate",
                    key="btn_generate_output",
                    help="Synthesise the discussion into a structured document",
                    use_container_width=True,
                    disabled=len(wmsgs) < 2,
                ):
                    st.session_state.show_output_panel = True
                    st.rerun()

                if st.button("📎 Upload File", key="btn_toggle_upload", use_container_width=True):
                    st.session_state["show_wr_upload"] = not st.session_state.get("show_wr_upload", False)
                    st.rerun()

                with st.expander("⚙️ More", expanded=False):
                    if st.button("🗄 Archive", key="archive_ws", help="Archive this workroom", use_container_width=True):
                        storage.archive_workroom(active_ws.id)
                        st.session_state.workroom_id = None
                        st.session_state.workroom_messages = []
                        st.rerun()
                    if st.button("🗑 Clear Chat", key="btn_clear_wr_chat", use_container_width=True):
                        st.session_state.workroom_messages = []
                        _save_workroom_messages(active_ws.id, [])
                        st.session_state.workroom_active_document = None
                        st.rerun()

                # ---- File upload (shown when toggled) ----
                if st.session_state.get("show_wr_upload", False):
                    wr_file = st.file_uploader(
                        "Upload a document for context",
                        type=["md", "txt", "pdf", "docx"],
                        key="wr_file_upload",
                        label_visibility="collapsed",
                    )
                    if wr_file is not None:
                        fkey = f"{wr_file.name}_{wr_file.size}"
                        if fkey not in st.session_state.workroom_file_keys:
                            st.session_state.workroom_file_keys.add(fkey)
                            fbytes = wr_file.read()
                            with st.spinner(f"Processing {wr_file.name}…"):
                                resp = orchestrator.handle_message(
                                    f"Uploaded: {wr_file.name}",
                                    file_bytes=fbytes,
                                    filename=wr_file.name,
                                    date=today_str,
                                    active_agents=active_ws.active_agents,
                                )
                            if resp.get("data") and resp["data"].get("document"):
                                st.session_state.workroom_active_document = resp["data"]["document"]
                                active_ws.document_context = resp["data"]["document"]
                                storage.save_workroom(active_ws)
                            wmsgs.append({"role": "user", "content": f"📎 Uploaded: {wr_file.name}"})
                            wmsgs.append({
                                "role": "assistant",
                                "content": resp["text"],
                                "agent": resp.get("agent", ""),
                            })
                            _save_workroom_messages(active_ws.id, wmsgs)
                            st.session_state.workroom_messages = wmsgs
                            st.session_state["show_wr_upload"] = False
                            st.rerun()

                # ---- Generate output panel ----
                if st.session_state.show_output_panel:
                    with st.expander(
                        "✨ Generate Output",
                        expanded=True,
                    ):
                        output_keys = list(OUTPUT_TYPE_META.keys())
                        current_idx = output_keys.index(active_ws.output_type) if active_ws.output_type in output_keys else 0
                        selected_output_type = st.selectbox(
                            "Output format",
                            output_keys,
                            index=current_idx,
                            format_func=lambda k: f"{OUTPUT_TYPE_META[k]['emoji']} {OUTPUT_TYPE_META[k]['label']}",
                            key="gen_output_type_select",
                            help="Change the output format before generating.",
                        )
                        sel_meta = OUTPUT_TYPE_META.get(selected_output_type, {})
                        if sel_meta.get("description"):
                            st.caption(sel_meta["description"])

                        custom_desc = ""
                        if selected_output_type == "custom":
                            custom_desc = st.text_input(
                                "Describe the output you want",
                                placeholder="e.g., A one-pager for the exec team",
                                key="custom_output_desc",
                            )
                        if st.button("⚡ Generate now", key="gen_output_now", type="primary", use_container_width=True):
                            if selected_output_type != active_ws.output_type:
                                active_ws.output_type = selected_output_type
                                storage.save_workroom(active_ws)
                            with st.spinner("Synthesising discussion…"):
                                doc_content = orchestrator.generate_output(
                                    output_type=selected_output_type,
                                    messages=wmsgs,
                                    workroom=active_ws,
                                    custom_description=custom_desc,
                                )
                            st.session_state["last_generated_output"] = doc_content
                            st.session_state.show_output_panel = False
                            st.rerun()
                        if st.button("Cancel", key="gen_output_cancel", use_container_width=True):
                            st.session_state.show_output_panel = False
                            st.rerun()

                st.divider()

                # ---- 📄 Last Generated Output ----
                if st.session_state.get("last_generated_output"):
                    with st.expander("📄 Last Output", expanded=False):
                        st.markdown(st.session_state["last_generated_output"])
                        st.download_button(
                            "⬇ Download .md",
                            data=st.session_state["last_generated_output"],
                            file_name=f"{active_ws.title.replace(' ', '_')}_output.md",
                            mime="text/markdown",
                            key="download_output",
                            use_container_width=True,
                        )
                        if st.button("✕ Dismiss", key="dismiss_output", use_container_width=True):
                            del st.session_state["last_generated_output"]
                            st.rerun()

                # ---- 📓 Decision Log ----
                active_ws_fresh = storage.get_workroom(active_ws.id)
                if active_ws_fresh and active_ws_fresh.decisions:
                    with st.expander(f"📓 Decisions ({len(active_ws_fresh.decisions)})", expanded=False):
                        for d in active_ws_fresh.decisions:
                            st.markdown(f"- **{d.made_at[:16].replace('T', ' ')}** — {d.content[:200]}")
                else:
                    with st.expander("📓 Decisions", expanded=False):
                        st.caption("No decisions recorded yet.")

                # ---- 📚 Past Outputs ----
                if active_ws_fresh and active_ws_fresh.generated_outputs:
                    with st.expander(f"📚 Past Outputs ({len(active_ws_fresh.generated_outputs)})", expanded=False):
                        for go in reversed(active_ws_fresh.generated_outputs):
                            st.markdown(f"**{go.generated_at[:16].replace('T', ' ')} — {go.title}**")
                            st.markdown(go.content[:500] + ("…" if len(go.content) > 500 else ""))
                            st.download_button(
                                "⬇ Download",
                                data=go.content,
                                file_name=f"{go.title.replace(' ', '_')}.md",
                                mime="text/markdown",
                                key=f"dl_go_{go.id}",
                            )
                            st.divider()
                else:
                    with st.expander("📚 Past Outputs", expanded=False):
                        st.caption("No outputs generated yet.")

            # ---- Chat input (MUST be outside st.columns) ----
            # Mention mode: set by clicking an agent button, stays active until Send/Cancel
            _new_mention = st.session_state.pop("wr_mention_prefix", "")
            if _new_mention:
                # Fresh click — store as active mention
                st.session_state["wr_mention_active"] = _new_mention

            _mention_active = st.session_state.get("wr_mention_active", "")

            disc_hint = {
                "open": "Type a message… or select an agent above",
                "round_table": "Type a message, then click 🔄 Round Table in the side panel",
                "focused": f"Talking to {active_ws.focused_agent or 'focused agent'} — type your message",
            }

            # Show mention indicator above the unified chat input
            if _mention_active:
                _agent_key = _mention_active.strip().lstrip("@")
                _a_map = _agent_label_map()
                _a_display = _a_map.get(_agent_key, _agent_key)
                _ind_col1, _ind_col2 = st.columns([6, 1])
                with _ind_col1:
                    st.caption(f"💬 Directing to **{_a_display}** — type your question below")
                with _ind_col2:
                    if st.button("✕", key="wr_mention_cancel", help="Cancel @mention"):
                        st.session_state.pop("wr_mention_active", None)
                        st.rerun()

            _placeholder = f"Ask {_a_display}…" if _mention_active else disc_hint.get(active_ws.discussion_mode, "Type a message…")
            wr_input = st.chat_input(_placeholder, key="wr_chat_input")

            # Prepend @mention prefix to the message if mention mode is active
            if wr_input and _mention_active:
                wr_input = f"{_mention_active}{wr_input}"
                st.session_state.pop("wr_mention_active", None)

            # ---- Process chat input (outside columns) ----
            # Two-phase approach: Phase 1 saves user msg + reruns so it appears
            # immediately. Phase 2 (next render) processes the agent response.
            if wr_input and not st.session_state.get("wr_pending_input"):
                # Phase 1: save user message and rerun to show it instantly
                wmsgs.append({"role": "user", "content": wr_input})
                _save_workroom_messages(active_ws.id, wmsgs)
                st.session_state.workroom_messages = wmsgs
                st.session_state.wr_pending_input = wr_input
                st.rerun()

            # Phase 2: pending input exists — get agent response
            _pending = st.session_state.pop("wr_pending_input", None)
            if _pending:
                try:
                    with st.spinner("Thinking…"):
                        if active_ws.discussion_mode == "round_table":
                            result = orchestrator.round_table(
                                _pending,
                                active_agents=active_ws.active_agents,
                                conversation_history=wmsgs[:-1],
                                document_context=st.session_state.workroom_active_document,
                                workroom=active_ws,
                            )
                            wmsgs.append({
                                "role": "assistant",
                                "content": result["text"],
                                "agent": "[Round Table]",
                                "multi_response": result.get("multi_response"),
                            })
                        elif active_ws.discussion_mode == "focused" and active_ws.focused_agent:
                            result = orchestrator._route_by_key(
                                active_ws.focused_agent,
                                _pending,
                                conversation_history=wmsgs[:-1],
                                document_context=st.session_state.workroom_active_document,
                                active_agents=active_ws.active_agents,
                            )
                            from agents.orchestrator import _is_decision
                            if _is_decision(result.get("text", "")):
                                from models.workroom import Decision as WRDecision
                                storage.add_workroom_decision(
                                    active_ws.id,
                                    WRDecision(content=result["text"][:300], context=_pending[:200])
                                )
                            wmsgs.append({
                                "role": "assistant",
                                "content": result.get("text", ""),
                                "agent": result.get("agent", ""),
                            })
                        else:
                            result = orchestrator.handle_message(
                                _pending,
                                file_bytes=None,
                                filename="",
                                date=today_str,
                                document_context=st.session_state.workroom_active_document,
                                conversation_history=wmsgs[:-1],
                                active_agents=active_ws.active_agents,
                                workroom=active_ws,
                            )
                            from agents.orchestrator import _is_decision
                            from models.workroom import Decision as WRDecision
                            if _is_decision(result.get("text", "")):
                                storage.add_workroom_decision(
                                    active_ws.id,
                                    WRDecision(content=result["text"][:300], context=_pending[:200])
                                )
                            wmsgs.append({
                                "role": "assistant",
                                "content": result.get("text", ""),
                                "agent": result.get("agent", ""),
                                "multi_response": result.get("multi_response"),
                            })
                except Exception as _chat_err:
                    import logging
                    logging.getLogger(__name__).exception("Workroom chat error: %s", _chat_err)
                    wmsgs.append({
                        "role": "assistant",
                        "content": "Something went wrong processing your message. Please try sending it again.",
                        "agent": "[System]",
                    })

                _save_workroom_messages(active_ws.id, wmsgs)
                st.session_state.workroom_messages = wmsgs

                # ---- Facilitator periodic summary ----
                try:
                    if active_ws.facilitator_enabled:
                        _user_msg_count = sum(1 for m in wmsgs if m.get("role") == "user")
                        _fac = FacilitatorAgent()
                        if _fac.should_summarise(_user_msg_count, active_ws.facilitator_summary_interval):
                            with st.spinner("Facilitator summarising…"):
                                _summary = _fac.generate_summary(wmsgs, active_ws.goal)
                            wmsgs.append({"role": "assistant", "content": _summary, "agent": "🎙️ Facilitator"})
                            _save_workroom_messages(active_ws.id, wmsgs)
                            st.session_state.workroom_messages = wmsgs
                except Exception:
                    pass  # Don't block chat over facilitator error

                st.rerun()

        # ================================================================
        # MODE B: Existing Workrooms listing
        # ================================================================
        else:
            st.markdown("### 💬 Existing Workrooms")

            _all_wrs = storage.list_workrooms(include_archived=False)

            if not _all_wrs:
                st.markdown(
                    '<div class="empty-state">'
                    '<div class="empty-state-icon">💬</div>'
                    '<div class="empty-state-text">No workrooms yet.<br>'
                    'Click <b>✨ New Workroom</b> in the sidebar to get started.</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption(f"{len(_all_wrs)} workroom{'s' if len(_all_wrs) != 1 else ''} — click to enter.")
                st.divider()

                for _ws in _all_wrs:
                    _mode_icon = "💼" if _ws.mode == "work" else "🎉"
                    _meta = OUTPUT_TYPE_META.get(_ws.output_type, {})
                    _msg_count = len(storage.load_workroom_messages(_ws.id))
                    _agent_count = len(_ws.active_agents)
                    _created = _ws.created_at[:10] if _ws.created_at else ""

                    with st.container():
                        _c1, _c2 = st.columns([4, 1])
                        with _c1:
                            st.markdown(f"#### {_mode_icon} {_ws.title}")
                            st.caption(
                                f"{_meta.get('emoji', '')} {_meta.get('label', '')}  ·  "
                                f"{_agent_count} agents  ·  "
                                f"{_msg_count} messages  ·  "
                                f"{len(_ws.decisions)} decisions  ·  "
                                f"Created {_created}"
                            )
                            if _ws.goal:
                                st.markdown(f"🎯 {_ws.goal[:150]}{'…' if len(_ws.goal) > 150 else ''}")
                        with _c2:
                            if st.button("Open →", key=f"open_wr_{_ws.id}", type="primary", use_container_width=True):
                                st.session_state.nav_page = "chat"
                                st.session_state.workroom_id = _ws.id
                                st.session_state.workroom_messages = _load_workroom_messages(_ws.id)
                                st.session_state.show_new_workroom_form = False
                                st.session_state.workroom_file_keys = set()
                                st.session_state.workroom_active_document = None
                                st.rerun()
                            if st.button("🗄 Archive", key=f"archive_wr_{_ws.id}", use_container_width=True):
                                storage.archive_workroom(_ws.id)
                                st.rerun()
                        st.divider()


# ================================================================== #
# PAGE: INSIGHTS                                                      #
# ================================================================== #

if page == "insights":
    col_header, col_filter1, col_filter2 = st.columns([2, 1, 1])
    with col_header:
        st.markdown("## 💡 Insights")
    with col_filter1:
        type_filter = st.selectbox(
            "Type",
            ["All", "risk", "trend", "gap", "decision"],
            key="insight_type_filter",
        )
    with col_filter2:
        period_filter = st.selectbox(
            "Period",
            ["All time", "Last 7 days", "Last 30 days"],
            key="insight_period_filter",
        )

    # Quick analysis buttons
    st.markdown('<div class="section-header">Quick Analysis</div>', unsafe_allow_html=True)
    qa_col1, qa_col2, qa_col3, qa_col4 = st.columns(4)

    def _prime_chat_and_run(prompt: str, intent: str):
        """Add a primed message to chat and trigger analysis."""
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.spinner(f"[Analyst] Running {intent} analysis..."):
            response = orchestrator.handle_message(prompt)
        st.session_state.messages.append({
            "role": "assistant",
            "content": response["text"],
            "agent": response.get("agent", ""),
            "warning": response.get("warning", ""),
        })
        storage.save_conversation(st.session_state.messages)

    with qa_col1:
        if st.button("📈 What's trending?", key="qa_trend", use_container_width=True):
            _prime_chat_and_run("What's trending in my customer requests?", "trend")
            st.rerun()
    with qa_col2:
        if st.button("🕳 What are we missing?", key="qa_gap", use_container_width=True):
            _prime_chat_and_run("What gaps are we missing in our customer requests?", "gap")
            st.rerun()
    with qa_col3:
        if st.button("⚠️ What's at risk?", key="qa_risk", use_container_width=True):
            _prime_chat_and_run("What's at risk of escalating?", "risk")
            st.rerun()
    with qa_col4:
        if st.button("🤔 Help me decide...", key="qa_decision", use_container_width=True):
            st.session_state["prime_decision"] = True
            st.rerun()

    if st.session_state.get("prime_decision"):
        decision_q = st.text_input(
            "What decision do you need help with?",
            placeholder="e.g., Should I prioritise webhook retry or audit logging first?",
            key="decision_question_input",
        )
        if decision_q:
            _prime_chat_and_run(f"Help me decide: {decision_q}", "decision")
            st.session_state["prime_decision"] = False
            st.rerun()

    st.divider()

    # Load and filter insights
    type_arg = None if type_filter == "All" else [type_filter]
    days_arg = None
    if period_filter == "Last 7 days":
        days_arg = 7
    elif period_filter == "Last 30 days":
        days_arg = 30

    insights = storage.list_insights(insight_type=type_arg, recent_days=days_arg)

    if not insights:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state-icon">💡</div>'
            '<div class="empty-state-text">No insights yet.<br>Use the quick analysis buttons above to generate your first insights.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"{len(insights)} insight(s)")
        for ins in insights:
            type_class = f"insight-{ins.insight_type}"
            status_icon = "🟢 In plan" if ins.in_day_plan else "🟡 Not yet acted on"
            confidence_color = {"high": "🔴", "medium": "🟠", "low": "🟡"}.get(
                ins.confidence, ""
            )

            with st.expander(
                f"{ins.insight_type.upper()} · {confidence_color} {ins.confidence.capitalize()} · {ins.created_at[:10]}  —  {ins.title}",
                expanded=False,
            ):
                st.markdown(
                    f'<div class="{type_class}">'
                    f"<strong>What:</strong> {ins.what}<br><br>"
                    f"<strong>Why:</strong> {ins.why}<br><br>"
                    f"<strong>Action:</strong> {ins.recommended_action}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Status:** {status_icon}")
                if ins.linked_request_ids:
                    st.caption(
                        f"Linked requests: {', '.join('#' + r for r in ins.linked_request_ids)}"
                    )
                st.caption(f"ID: {ins.id} · Period: {ins.period}")


# ================================================================== #
# PAGE: REQUESTS                                                      #
# ================================================================== #

if page == "requests":
    col_header, col_add, col_upload = st.columns([3, 1, 1])
    with col_header:
        st.markdown("## 📋 Requests")
    with col_add:
        show_add_form = st.button("➕ Add request", key="show_add_form", use_container_width=True)
    with col_upload:
        show_upload = st.button("⬆ Upload file", key="show_upload", use_container_width=True)

    if "show_add_form_state" not in st.session_state:
        st.session_state.show_add_form_state = False
    if show_add_form:
        st.session_state.show_add_form_state = not st.session_state.show_add_form_state

    if "show_upload_state" not in st.session_state:
        st.session_state.show_upload_state = False
    if show_upload:
        st.session_state.show_upload_state = not st.session_state.show_upload_state

    # Add request inline form
    if st.session_state.show_add_form_state:
        with st.container():
            st.markdown("**New request**")
            with st.form("add_request_form"):
                req_description = st.text_area(
                    "Description *",
                    placeholder="e.g., Stripe need webhook retry logic — blocking production rollout",
                    height=80,
                )
                req_source = st.selectbox(
                    "Source",
                    ["chat", "csv", "pdf", "docx", "copilot_briefing"],
                    index=0,
                )
                submitted = st.form_submit_button("Save request", type="primary")
                if submitted:
                    if req_description.strip():
                        with st.spinner("[Intake] Classifying request..."):
                            from agents.intake_agent import IntakeAgent
                            intake = IntakeAgent(storage)
                            req = intake.classify_request(
                                req_description.strip(),
                                source=req_source,
                                source_ref="form",
                            )
                        st.success(
                            f"Saved #{req.id} — {req.priority} {req.classification}"
                        )
                        st.session_state.show_add_form_state = False
                        st.rerun()
                    else:
                        st.error("Description is required.")

    # Upload file form
    if st.session_state.show_upload_state:
        with st.container():
            st.markdown("**Bulk import**")
            bulk_file = st.file_uploader(
                "Upload CSV, PDF, or Word file",
                type=["csv", "pdf", "docx"],
                key="bulk_import_upload",
            )
            if bulk_file:
                with st.spinner("[Intake] Processing file..."):
                    file_bytes = bulk_file.read()
                    pending_requests = orchestrator.intake.process_bulk_file(
                        file_bytes, filename=bulk_file.name
                    )

                if pending_requests:
                    st.markdown(f"**Found {len(pending_requests)} request(s):**")
                    for i, req in enumerate(pending_requests[:10], 1):
                        st.markdown(
                            f"{i}. [{req.priority}] **{req.classification}**: {req.description}"
                        )
                    if len(pending_requests) > 10:
                        st.caption(f"...and {len(pending_requests) - 10} more")

                    if st.button("✅ Save all requests", key="save_bulk"):
                        saved = orchestrator.intake.save_requests(pending_requests)
                        st.success(f"Saved {len(saved)} requests.")
                        st.session_state.show_upload_state = False
                        st.rerun()
                else:
                    st.warning("No requests found in the file.")

    st.divider()

    # Filters
    fcol1, fcol2, fcol3, fcol4 = st.columns([1, 1, 1, 2])
    with fcol1:
        priority_filter = st.multiselect(
            "Priority",
            ["P0", "P1", "P2", "P3"],
            key="req_priority_filter",
        )
    with fcol2:
        status_filter = st.multiselect(
            "Status",
            ["new", "triaged", "in_review", "linked", "closed"],
            key="req_status_filter",
        )
    with fcol3:
        type_req_filter = st.multiselect(
            "Type",
            ["feature_request", "bug_report", "integration", "support", "feedback"],
            key="req_type_filter",
        )
    with fcol4:
        search_text = st.text_input("🔍 Search", placeholder="Search descriptions...", key="req_search")

    # Load requests
    all_reqs = storage.list_requests(
        priority=priority_filter if priority_filter else None,
        status=status_filter if status_filter else None,
    )

    if type_req_filter:
        all_reqs = [r for r in all_reqs if r.classification in type_req_filter]
    if search_text.strip():
        q = search_text.strip().lower()
        all_reqs = [r for r in all_reqs if q in r.description.lower() or q in r.raw_input.lower()]

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    all_reqs.sort(key=lambda r: (priority_order.get(r.priority, 99), r.created_at), reverse=False)
    all_reqs.sort(key=lambda r: priority_order.get(r.priority, 99))

    # Stats row
    total_reqs = len(all_reqs)
    p0 = sum(1 for r in all_reqs if r.priority == "P0")
    p1 = sum(1 for r in all_reqs if r.priority == "P1")
    new_count = sum(1 for r in all_reqs if r.status == "new")

    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        st.markdown(
            f'<div class="stat-card"><div class="stat-value">{total_reqs}</div>'
            f'<div class="stat-label">Total</div></div>',
            unsafe_allow_html=True,
        )
    with sc2:
        st.markdown(
            f'<div class="stat-card"><div class="stat-value" style="color:#dc2626;">{p0}</div>'
            f'<div class="stat-label">P0 Critical</div></div>',
            unsafe_allow_html=True,
        )
    with sc3:
        st.markdown(
            f'<div class="stat-card"><div class="stat-value" style="color:#ea580c;">{p1}</div>'
            f'<div class="stat-label">P1 High</div></div>',
            unsafe_allow_html=True,
        )
    with sc4:
        st.markdown(
            f'<div class="stat-card"><div class="stat-value">{new_count}</div>'
            f'<div class="stat-label">New / Untriaged</div></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    if not all_reqs:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state-icon">📋</div>'
            '<div class="empty-state-text">No requests yet.<br>Add one above or use Chat to log requests.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        # Table header
        hcol1, hcol2, hcol3, hcol4, hcol5 = st.columns([1, 1, 1.5, 0.8, 3])
        with hcol1:
            st.markdown("**ID**")
        with hcol2:
            st.markdown("**Priority**")
        with hcol3:
            st.markdown("**Type**")
        with hcol4:
            st.markdown("**Surfaced**")
        with hcol5:
            st.markdown("**Description**")

        st.divider()

        for req in all_reqs:
            r1, r2, r3, r4, r5 = st.columns([1, 1, 1.5, 0.8, 3])
            with r1:
                st.code(f"#{req.id}", language=None)
            with r2:
                st.markdown(
                    f'<span class="badge-{req.priority}">{req.priority}</span>',
                    unsafe_allow_html=True,
                )
            with r3:
                st.caption(req.classification.replace("_", " ").title())
            with r4:
                surfaced = req.surface_count
                if surfaced == 0:
                    st.caption("🔘 Never")
                else:
                    st.caption(f"🟢 {surfaced}×")
            with r5:
                with st.expander(req.description[:80] + ("..." if len(req.description) > 80 else "")):
                    st.markdown(f"**Description:** {req.description}")
                    st.markdown(f"**Priority rationale:** {req.priority_rationale}")
                    st.markdown(f"**Classification rationale:** {req.classification_rationale}")
                    if req.tags:
                        st.markdown(f"**Tags:** {', '.join(req.tags)}")
                    st.caption(
                        f"Status: {req.status} · Created: {req.created_at[:10]} · "
                        f"Source: {req.source} ({req.source_ref})"
                    )
                    if req.linked_insight_ids:
                        st.caption(f"Linked insights: {', '.join(req.linked_insight_ids)}")

                    new_status = st.selectbox(
                        "Update status",
                        ["new", "triaged", "in_review", "linked", "closed"],
                        index=["new", "triaged", "in_review", "linked", "closed"].index(req.status),
                        key=f"status_{req.id}",
                    )
                    if new_status != req.status:
                        req.update_field("status", new_status)
                        storage.save_request(req)
                        st.success(f"Updated #{req.id} status to {new_status}")
                        st.rerun()

                    if st.button("🗑 Archive", key=f"delete_{req.id}"):
                        storage.soft_delete_request(req.id)
                        st.warning(f"Archived #{req.id}")
                        st.rerun()


# ================================================================== #
# PAGE: AGENT HUB (Settings)                                          #
# ================================================================== #

if page == "agent_hub":
    st.markdown("## 🤖 Agent Hub")
    st.caption("Manage your agent library. Changes here apply system-wide across all workrooms and chat.")

    st.divider()

    # ---- All agents ----
    all_agents = storage.list_custom_agents()

    # -- Category display helpers --
    _CATEGORY_META = {
        "pm_workflow": {"label": "PM Workflow", "emoji": "🧭", "css": "pm_workflow"},
        "ai_product":  {"label": "AI Product",  "emoji": "🤖", "css": "ai_product"},
        "career":      {"label": "Career",      "emoji": "💼", "css": "career"},
        "life":        {"label": "Life",        "emoji": "🎉", "css": "life"},
    }
    # Backward-compat: old stored agents with "professional" resolve to pm_workflow
    _CATEGORY_ALIAS = {"professional": "pm_workflow"}

    def _category_badge(cat: str) -> str:
        resolved = _CATEGORY_ALIAS.get(cat, cat)
        meta = _CATEGORY_META.get(resolved)
        if meta:
            return (
                f'<span class="agent-card-category agent-card-category--{meta["css"]}">'
                f'{meta["emoji"]} {meta["label"]}</span>'
            )
        label = resolved.capitalize() if resolved else "Custom"
        return f'<span class="agent-card-category agent-card-category--custom">✨ {label}</span>'

    def _source_tag(ca) -> str:
        if ca.is_default:
            return '<span class="agent-card-tag agent-card-tag--default">DEFAULT</span>'
        return '<span class="agent-card-tag agent-card-tag--custom">CUSTOM</span>'

    def _render_agent_card_html(ca) -> str:
        """Return the HTML for a single agent card."""
        desc_text = ca.description or ca.system_prompt[:100]
        return (
            f'<div class="agent-card">'
            f'  {_category_badge(ca.category)}'
            f'  <div class="agent-card-emoji">{ca.emoji}</div>'
            f'  <div class="agent-card-header">'
            f'    <span class="agent-card-name">{ca.label}</span>'
            f'    <span class="agent-card-key">@{ca.key}</span>'
            f'    {_source_tag(ca)}'
            f'  </div>'
            f'  <div class="agent-card-desc">{desc_text}</div>'
            f'</div>'
        )

    CARDS_PER_ROW = 3

    def _render_agent_section(label: str, agents: list):
        """Render a section of agent cards in a responsive column grid."""
        if not agents:
            return
        st.markdown(f'<div class="section-header">{label}</div>', unsafe_allow_html=True)

        # Render cards in rows of CARDS_PER_ROW using st.columns
        for row_start in range(0, len(agents), CARDS_PER_ROW):
            row_agents = agents[row_start : row_start + CARDS_PER_ROW]
            cols = st.columns(CARDS_PER_ROW)
            for idx, ca in enumerate(row_agents):
                with cols[idx]:
                    # Card visual
                    st.markdown(_render_agent_card_html(ca), unsafe_allow_html=True)
                    # Action buttons
                    is_editing = st.session_state.editing_agent_id == ca.id
                    if ca.is_default:
                        b1, _ = st.columns([1, 1])
                    else:
                        b1, b2 = st.columns(2)
                    with b1:
                        edit_label = "Close" if is_editing else "✏️ Edit"
                        if st.button(edit_label, key=f"edit_ca_{ca.id}", use_container_width=True):
                            st.session_state.editing_agent_id = None if is_editing else ca.id
                            st.rerun()
                    if not ca.is_default:
                        with b2:
                            if st.button("🗑 Delete", key=f"del_ca_{ca.id}", use_container_width=True):
                                storage.delete_custom_agent(ca.id)
                                if st.session_state.editing_agent_id == ca.id:
                                    st.session_state.editing_agent_id = None
                                st.rerun()

        # Edit forms rendered full-width below the grid (forms need space)
        for ca in agents:
            if st.session_state.editing_agent_id == ca.id:
                st.markdown(f"**Editing {ca.emoji} {ca.label}**")
                with st.form(f"edit_agent_form_{ca.id}"):
                    new_prompt = st.text_area(
                        "System prompt",
                        value=ca.system_prompt,
                        height=180,
                        key=f"prompt_ta_{ca.id}",
                    )
                    save_btn = st.form_submit_button("💾 Save Changes", type="primary")
                    if save_btn:
                        if new_prompt.strip():
                            ca.system_prompt = new_prompt.strip()
                            storage.save_custom_agent(ca)
                            st.session_state.editing_agent_id = None
                            st.success(f"Updated {ca.emoji} {ca.label}")
                            st.rerun()
                        else:
                            st.error("System prompt cannot be empty.")

    # ---- Dynamic sections — group by effective category ----
    from collections import defaultdict as _defaultdict
    _cat_map = _defaultdict(list)
    for _a in all_agents:
        _effective = _CATEGORY_ALIAS.get(_a.category, _a.category) or ""
        _cat_map[_effective].append(_a)

    # Well-known categories render first in defined order
    _KNOWN_ORDER = ["pm_workflow", "ai_product", "career", "life"]
    _rendered_cats = set()
    for _cat in _KNOWN_ORDER:
        if _cat in _cat_map:
            _m = _CATEGORY_META[_cat]
            _render_agent_section(f"{_m['emoji']} {_m['label']}", _cat_map[_cat])
            _rendered_cats.add(_cat)

    # Remaining categories rendered alphabetically (auto-generated sections)
    for _cat in sorted(_cat_map.keys()):
        if _cat not in _rendered_cats:
            _lbl = _cat.capitalize() if _cat else "Uncategorised"
            _render_agent_section(f"✨ {_lbl}", _cat_map[_cat])

    st.divider()

    # ---- Add Agents ----
    st.markdown("### Add Agents")

    hub_btn_col1, hub_btn_col2 = st.columns(2)
    with hub_btn_col1:
        if st.button("🔍 Explore Experts", key="explore_experts_btn", type="primary", use_container_width=True):
            st.session_state.show_explore_form = not st.session_state.show_explore_form
            st.session_state.show_custom_agent_form = False
            if not st.session_state.show_explore_form:
                # Closing the pane — clear results
                st.session_state.explore_results = None
                st.session_state.explore_selected = {}
            st.rerun()
    with hub_btn_col2:
        if st.button("➕ Create Manually", key="add_custom_agent_btn", use_container_width=True):
            st.session_state.show_custom_agent_form = not st.session_state.show_custom_agent_form
            st.session_state.show_explore_form = False
            st.session_state.explore_results = None
            st.session_state.explore_selected = {}
            st.rerun()

    # ---- Explore Experts pane ----
    if st.session_state.show_explore_form:
        st.caption("Describe a challenge or topic and we'll suggest the right specialists.")

        explore_problem = st.text_area(
            "What problem or challenge do you need help with?",
            height=100,
            placeholder="e.g., We need to decide whether to build or buy a recommendation engine for our platform.",
            key="explore_problem_input",
        )

        if st.button("Find Experts", key="find_experts_btn", type="primary"):
            if not explore_problem.strip():
                st.error("Please describe your problem or challenge first.")
            else:
                with st.spinner("Exploring domain expertise needed..."):
                    designer = AgentDesigner()
                    result = designer.design(explore_problem.strip())

                if not result["agents"]:
                    st.error("Could not generate agent suggestions. Please try rephrasing your problem.")
                else:
                    st.session_state.explore_results = result
                    # Default duplicates to unchecked, new agents to checked
                    existing_keys = {a.key for a in storage.list_custom_agents()}
                    st.session_state.explore_selected = {
                        a["key"]: (a["key"] not in existing_keys)
                        for a in result["agents"]
                    }
                    st.rerun()

        # ---- Results review ----
        if st.session_state.explore_results:
            result = st.session_state.explore_results

            # Show reasoning — the WHY
            if result.get("reasoning"):
                st.info(result["reasoning"])

            st.markdown("**Proposed Specialists** — review and select which to add:")

            # Pre-compute existing keys once for the render loop
            _existing_keys = {a.key for a in storage.list_custom_agents()}

            # One card per proposed agent
            for agent in result["agents"]:
                key = agent["key"]
                is_duplicate = key in _existing_keys
                current_checked = st.session_state.explore_selected.get(key, not is_duplicate)

                agent_col1, agent_col2 = st.columns([0.08, 0.92])
                with agent_col1:
                    checked = st.checkbox(
                        label=agent.get("label", key),
                        value=current_checked,
                        key=f"explore_check_{key}",
                        label_visibility="collapsed",
                    )
                    st.session_state.explore_selected[key] = checked
                with agent_col2:
                    duplicate_badge = (
                        " &nbsp;<span style='font-size:0.75em; color:#e07b39; "
                        "background:#fff3e0; padding:1px 6px; border-radius:4px; "
                        "font-weight:600;'>Already in library</span>"
                        if is_duplicate else ""
                    )
                    st.markdown(
                        f"**{agent['emoji']} {agent['label']}**{duplicate_badge}  \n"
                        f"<span style='color: #888; font-size: 0.85em;'>{agent.get('description', '')}</span>",
                        unsafe_allow_html=True,
                    )
                    with st.expander("View system prompt", expanded=False):
                        edited_prompt = st.text_area(
                            "System prompt",
                            value=agent["system_prompt"],
                            height=140,
                            key=f"explore_prompt_{key}",
                            label_visibility="collapsed",
                        )
                        # Keep edited prompt in sync with results
                        agent["system_prompt"] = edited_prompt

            # Save button — count selected
            selected_count = sum(1 for v in st.session_state.explore_selected.values() if v)
            save_label = f"💾 Save {selected_count} Selected Agent{'s' if selected_count != 1 else ''}"

            if st.button(save_label, key="save_explore_agents_btn", type="primary", disabled=selected_count == 0):
                existing_keys = {a.key for a in storage.list_custom_agents()}
                saved = []
                for agent in result["agents"]:
                    if not st.session_state.explore_selected.get(agent["key"], False):
                        continue
                    # Dedup key if it already exists in library
                    final_key = agent["key"]
                    if final_key in existing_keys:
                        final_key = f"{final_key}_2"
                    # Use the (possibly edited) prompt from session state
                    prompt_key = f"explore_prompt_{agent['key']}"
                    final_prompt = st.session_state.get(prompt_key, agent["system_prompt"])
                    new_ca = CustomAgent(
                        key=final_key,
                        label=agent["label"],
                        emoji=agent["emoji"],
                        description=agent.get("description", ""),
                        system_prompt=final_prompt.strip() or agent["system_prompt"],
                        category=agent.get("category", "professional"),
                    )
                    storage.save_custom_agent(new_ca)
                    saved.append(f"{new_ca.emoji} {new_ca.label}")

                # Clear explore state
                st.session_state.explore_results = None
                st.session_state.explore_selected = {}
                st.session_state.show_explore_form = False
                if saved:
                    st.success(f"Added {len(saved)} agent{'s' if len(saved) != 1 else ''}: {', '.join(saved)}")
                st.rerun()

    # ---- Create Manually pane ----
    if st.session_state.show_custom_agent_form:
        st.caption("Create a new agent with a custom persona and system prompt.")
        with st.form("custom_agent_form"):
            ca_col1, ca_col2 = st.columns(2)
            with ca_col1:
                ca_label = st.text_input("Name *", placeholder="e.g., Growth Hacker")
                ca_key = st.text_input("Key (for @mention) *", placeholder="e.g., growth")
            with ca_col2:
                ca_emoji = st.text_input("Emoji", value="🤖", max_chars=2)
                ca_description = st.text_input("Short description", placeholder="e.g., Focuses on growth loops and acquisition")

            _KNOWN_CAT_OPTIONS = [
                ("pm_workflow", "🧭 PM Workflow"),
                ("ai_product",  "🤖 AI Product"),
                ("career",      "💼 Career"),
                ("life",        "🎉 Life"),
                ("other",       "✨ Other (specify below)"),
            ]
            ca_category_key = st.selectbox(
                "Category",
                options=[k for k, _ in _KNOWN_CAT_OPTIONS],
                format_func=lambda x: dict(_KNOWN_CAT_OPTIONS)[x],
            )
            ca_category_custom = ""
            if ca_category_key == "other":
                ca_category_custom = st.text_input(
                    "Category name",
                    placeholder="e.g., legal, creative, marketing",
                    key="ca_custom_category",
                )
            ca_category = (
                ca_category_custom.strip().lower()
                if ca_category_key == "other" and ca_category_custom.strip()
                else (ca_category_key if ca_category_key != "other" else "")
            )

            ca_prompt = st.text_area(
                "System prompt *",
                height=150,
                placeholder="You are a growth strategist. You focus on user acquisition, activation, retention...",
            )

            ca_submit = st.form_submit_button("💾 Save Agent", type="primary")
            if ca_submit:
                if ca_label.strip() and ca_key.strip() and ca_prompt.strip():
                    new_ca = CustomAgent(
                        key=ca_key.strip().lower().replace(" ", "_"),
                        label=ca_label.strip(),
                        emoji=ca_emoji.strip() or "🤖",
                        description=ca_description.strip(),
                        system_prompt=ca_prompt.strip(),
                        category=ca_category,
                    )
                    storage.save_custom_agent(new_ca)
                    st.session_state.show_custom_agent_form = False
                    st.success(f"Created {new_ca.emoji} {new_ca.label}!")
                    st.rerun()
                else:
                    st.error("Name, key, and system prompt are required.")
