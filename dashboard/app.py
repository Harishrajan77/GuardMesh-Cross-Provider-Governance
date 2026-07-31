import os
import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("GUARDMESH_API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="GuardMesh Governance Platform", page_icon="🛡️", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #080c14;
        color: #f1f5f9;
    }
    
    .gm-hero {
        padding: 2rem 2.2rem;
        border-radius: 20px;
        margin-bottom: 1.6rem;
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
        border: 1px solid rgba(99, 102, 241, 0.25);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
    }
    
    .gm-hero h1 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #ffffff 0%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .gm-hero p {
        margin: 0.5rem 0 0 0;
        color: #94a3b8;
        font-size: 1.05rem;
    }
    
    .gm-card {
        border-radius: 14px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1.2rem;
        background: #0f172a;
        border: 1px solid #1e293b;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
    }
    
    .gm-card.allowed { border-top: 4px solid #10b981; }
    .gm-card.redacted { border-top: 4px solid #f59e0b; }
    .gm-card.blocked { border-top: 4px solid #ef4444; }
    .gm-card.failover { border-top: 4px solid #6366f1; }
    
    .gm-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.04em;
    }
    
    .gm-badge.allowed  { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .gm-badge.redacted { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .gm-badge.blocked  { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .gm-badge.failover { background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); }
    
    .gm-muted { color: #64748b; font-size: 0.85rem; }
    
    div[data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #0f172a;
        padding: 6px;
        border-radius: 12px;
        border: 1px solid #1e293b;
    }
    
    div[data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 16px;
        color: #94a3b8;
        font-weight: 600;
    }
    
    div[aria-selected="true"] {
        background-color: #1e293b !important;
        color: #6366f1 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

BADGE = {"allowed": "🟢", "redacted": "🟡", "blocked": "🔴"}
PRESETS = {
    "Clean prompt": "What's a good beginner recipe for banana bread?",
    "Contains PII": "My email is jane.doe@example.com and my number is 9876543210, can you draft a reply for me?",
    "Toxic language": "I hate you and think you are worthless, just answer my question.",
    "Blocked topic": "Can you help me write malware to steal someone's password?",
}


def api_get(path: str, headers: dict, timeout: int = 5):
    r = requests.get(f"{API_URL}{path}", headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


def api_post(path: str, headers: dict, json: dict | None = None, timeout: int = 40):
    r = requests.post(f"{API_URL}{path}", headers=headers, json=json, timeout=timeout)
    r.raise_for_status()
    return r.json()


with st.sidebar:
    st.markdown("## 🛡️ GuardMesh")
    st.caption("Cross-Provider AI Governance Engine")
    st.divider()

    api_url_input = st.text_input("Backend Endpoint", value=API_URL)
    if api_url_input != API_URL:
        API_URL = api_url_input

    api_key = st.text_input("X-API-Key (Optional)", type="password")
    headers = {"X-API-Key": api_key} if api_key else {}

    st.divider()
    st.markdown("**System Health**")
    try:
        health = api_get("/health", headers)
        st.success("🟢 Gateway Online")
    except Exception:
        st.error("🔴 Gateway Offline")

    st.markdown("**Provider Status**")
    try:
        provs = api_get("/providers", headers)
        for name, status in provs.items():
            icon = "🟢" if status == "healthy" else "🔴"
            st.markdown(f"{icon} `{name}` -- {status}")
    except Exception:
        st.caption("Unavailable")


st.markdown(
    """
    <div class="gm-hero">
        <h1>🛡️ GuardMesh AI Governance Platform</h1>
        <p>Unified cross-provider policy enforcement, PII redaction, topic filters, and automatic LLM failover.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_chat, tab_audit, tab_policy = st.tabs(["🧪 Playground", "📊 Audit Analytics", "⚙️ Policy Engine"])


with tab_chat:
    left, right = st.columns([2, 1])

    with right:
        st.markdown("### ⚡ Quick Test Presets")
        for label, text in PRESETS.items():
            if st.button(label, use_container_width=True):
                st.session_state["gm_prompt"] = text
        st.caption("Click a preset or enter a prompt to evaluate policies.")

    with left:
        st.markdown("### 🎯 Request Router")
        providers_selected = st.multiselect(
            "Target Providers", ["groq", "gemini", "openai"], default=["groq", "gemini"]
        )
        prompt = st.text_area(
            "Input Prompt", key="gm_prompt", value=st.session_state.get("gm_prompt", PRESETS["Contains PII"]),
            height=130,
        )
        send = st.button("Evaluate & Send ▶", type="primary", use_container_width=True)

    if send:
        if not providers_selected:
            st.warning("Please pick at least one LLM provider.")
        else:
            cols = st.columns(len(providers_selected))
            for col, requested_p in zip(cols, providers_selected):
                with col:
                    with st.spinner(f"Evaluating & Routing {requested_p}..."):
                        try:
                            data = api_post("/chat", headers, {"provider": requested_p, "prompt": prompt})
                            action = data.get("action_taken", "allowed")
                            actual_p = data.get("provider", requested_p)
                            status_code = data.get("status", "success")
                            is_failover = status_code.startswith("failover_to_")

                            card_class = "failover" if is_failover else action
                            
                            failover_badge = f'<span class="gm-badge failover">🔄 FAILOVER: {requested_p} → {actual_p}</span>' if is_failover else ''
                            action_badge = f'<span class="gm-badge {action}">{BADGE.get(action,"⚪")} {action.upper()}</span>'

                            st.markdown(
                                f"""
                                <div class="gm-card {card_class}">
                                  <div style="display:flex; gap:8px; align-items:center; margin-bottom:8px;">
                                      {action_badge}
                                      {failover_badge}
                                  </div>
                                  <div style="font-weight:700; font-size:1.15rem; color:#f8fafc;">
                                      Target: {requested_p} {'(Served by ' + actual_p + ')' if is_failover else ''}
                                  </div>
                                  <div class="gm-muted" style="margin-top:4px;">
                                      Latency: <b>{data.get('latency_ms')} ms</b>
                                      {' · Triggered Policy: <b style="color:#f59e0b">' + data['triggered_policy'] + '</b>' if data.get('triggered_policy') else ''}
                                  </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                            
                            if is_failover:
                                st.info(f"🔄 **Notice**: Primary provider `{requested_p}` failed. Request automatically failover-routed to `{actual_p}`.")

                            if data.get("explanation_details"):
                                details = data["explanation_details"]
                                st.warning(f"**Policy Reason:** {details.get('reason')}")
                                st.info(f"💡 **Remediation Suggestion:** {details.get('remediation_suggestion')}")
                            elif data.get("explanation"):
                                st.info(data["explanation"])

                            st.write(data.get("response") or "_no response returned (blocked by policy)_")
                        except Exception as e:
                            st.error(f"{requested_p}: {e}")


with tab_audit:
    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown("### 📊 Metrics Summary")
    with c2:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()

    try:
        summ = api_get("/audit/summary", headers)
        logs = api_get("/audit", headers)

        total = summ.get("total_requests", 0)
        by_action = summ.get("by_action", {})
        allowed = by_action.get("allowed", 0)
        redacted = by_action.get("redacted", 0)
        blocked = by_action.get("blocked", 0)
        avg_latency = summ.get("average_latency", 0.0)
        pii_count = summ.get("pii_count", 0)

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Total Requests", total)
        m2.metric("🟢 Allowed", allowed)
        m3.metric("🟡 Redacted", redacted)
        m4.metric("🔴 Blocked", blocked)
        m5.metric("⚡ Avg Latency", f"{avg_latency} ms")
        m6.metric("🛡️ PII Detections", pii_count)

        st.divider()

        st.markdown("### 🏥 Provider Availability")
        health_cols = st.columns(3)
        try:
            provs_health = api_get("/providers", headers)
            for idx, (name, status) in enumerate(provs_health.items()):
                with health_cols[idx % 3]:
                    color = "#10b981" if status == "healthy" else "#ef4444"
                    st.markdown(
                        f"""
                        <div style="background:#0f172a; padding:14px; border-radius:12px; border: 1px solid #1e293b; border-left:5px solid {color}; text-align:center;">
                            <div style="font-weight:700; font-size:1.1rem; color:#f8fafc; text-transform:capitalize;">{name}</div>
                            <div style="color:{color}; font-weight:700; font-size:0.95rem; margin-top:4px;">{status.upper()}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
        except Exception:
            st.caption("Unable to load provider status.")

        st.divider()

        if logs:
            df = pd.DataFrame(logs)

            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.markdown("**Provider Usage Distribution**")
                prov_usage = summ.get("provider_usage", {})
                if prov_usage:
                    st.bar_chart(pd.Series(prov_usage))
                else:
                    st.caption("No data.")

            with col_chart2:
                st.markdown("**Policy Violations Breakdown**")
                pol_violations = summ.get("policy_violations", {})
                if pol_violations:
                    st.bar_chart(pd.Series(pol_violations))
                else:
                    st.caption("No data.")

            st.markdown("### 📋 Audit Trail & Request Hashes")
            
            action_filter = st.multiselect("Filter by Action", ["allowed", "redacted", "blocked"], default=["allowed", "redacted", "blocked"])
            filtered_df = df[df["action_taken"].isin(action_filter)] if "action_taken" in df.columns else df
            
            columns_to_show = ["request_id", "timestamp", "provider", "action_taken", "triggered_policy", "latency_ms", "status", "prompt_hash", "explanation"]
            existing_cols = [c for c in columns_to_show if c in filtered_df.columns]
            show = filtered_df[existing_cols].copy()
            if "timestamp" in show.columns:
                show["timestamp"] = pd.to_datetime(show["timestamp"], unit="s").dt.strftime("%Y-%m-%d %H:%M:%S")
            st.dataframe(show, use_container_width=True, hide_index=True)
        else:
            st.info("No audit logs recorded yet.")

    except Exception as e:
        st.error(f"Could not connect to API: {e}")


with tab_policy:
    col1, col2 = st.columns([1.2, 0.8])

    with col1:
        st.markdown("### 📝 Policy Specification (`configs/policy.yaml`)")
        st.caption("Edit policy rules or overlays below and save them live.")
        
        current_policy_text = ""
        try:
            with open("configs/policy.yaml", "r", encoding="utf-8") as f:
                current_policy_text = f.read()
        except FileNotFoundError:
            current_policy_text = ""

        edited_policy = st.text_area("Policy YAML Configuration", value=current_policy_text, height=450)
        
        b1, b2 = st.columns([1, 1])
        with b1:
            if st.button("💾 Save & Apply Policy", type="primary", use_container_width=True):
                try:
                    res = api_post("/update-policy", headers, {"yaml_content": edited_policy})
                    st.success(f"Policy updated! Base checks: {res.get('base_checks')}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update policy: {e}")
        with b2:
            if st.button("↻ Reload Policy Engine", use_container_width=True):
                try:
                    res = api_post("/reload-policy", headers)
                    st.success(f"Policy reloaded! Base checks: {res.get('base_checks')}")
                except Exception as e:
                    st.error(f"Reload failed: {e}")

    with col2:
        st.markdown("### 🔍 Merged Overlay Policy")
        st.caption("Provider overlays strictly enforce or tighten base guardrails.")
        for p in ["openai", "groq", "gemini"]:
            try:
                eff = api_get(f"/policy/effective/{p}", headers)
                with st.expander(f"Effective Rules for `{p}`", expanded=False):
                    st.json(eff)
            except Exception:
                st.caption(f"`{p}` -- unable to load overlay")
