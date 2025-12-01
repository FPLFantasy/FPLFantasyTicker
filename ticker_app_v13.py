# ticker_app_v14.py — Pure Browser Local Storage Version
# ------------------------------------------------------
# Differences from v13:
# - REMOVED all persistent disk saving (CSV, volumes, env vars)
# - REMOVED atomic_save_difficulties(), load_from_disk(), /data, Railway volume usage
# - ADDED browser-local-storage persistence (per user, no login required)
# - All users keep their own Home/Away difficulties in their own browser

import streamlit as st
import pandas as pd
import numpy as np
import requests
from typing import Tuple, Dict, List
from matplotlib import cm, colors

# ✅ CORRECT IMPORT
from streamlit_browser_storage import st_browser_storage

st.set_page_config(layout="wide", page_title="FPL Season Ticker v14")

# ---------------------
# Browser Local Storage
# ---------------------
# ✅ CORRECT INITIALIZATION
local_store = st_browser_storage(key="user_difficulties_v14")

# ---------------------
# API endpoints
# ---------------------
FIX_API = "https://fantasy.premierleague.com/api/fixtures/"
BOOT_API = "https://fantasy.premierleague.com/api/bootstrap-static/"

# ---------------------
# Utility: load data
# ---------------------
@st.cache_data(ttl=3600)
def load_fpl_data() -> Tuple[pd.DataFrame, List[str], Dict[int, Dict[str,str]]]:
    try:
        r_fix = requests.get(FIX_API, timeout=10)
        r_fix.raise_for_status()
        fixtures = r_fix.json()
    except Exception:
        return pd.DataFrame(), [], {}

    try:
        r_boot = requests.get(BOOT_API, timeout=10)
        r_boot.raise_for_status()
        boot = r_boot.json()
    except Exception:
        boot = {}

    teams: Dict[int, Dict[str,str]] = {}
    if isinstance(boot, dict) and boot.get("teams"):
        try:
            for t in boot["teams"]:
                tid = int(t.get("id"))
                code = t.get("short_name") or (t.get("name", "")[:3])
                code = (str(code)[:3] if code else "").upper()
                teams[tid] = {"name": t.get("name", ""), "short": code}
        except Exception:
            teams = {}

    if not teams and isinstance(fixtures, list) and fixtures:
        ids = set()
        for f in fixtures:
            try:
                if isinstance(f.get("team_h"), (int, float)):
                    ids.add(int(f["team_h"]))
                if isinstance(f.get("team_a"), (int, float)):
                    ids.add(int(f["team_a"]))
            except Exception:
                continue
        for tid in ids:
            teams[int(tid)] = {"name": f"Team {tid}", "short": str(tid)[:3].upper()}

    rows = []
    for f in fixtures:
        try:
            if f.get("event") is None:
                continue
            team_h = f.get("team_h")
            team_a = f.get("team_a")
            if team_h not in teams and isinstance(team_h, (int, float)):
                teams[int(team_h)] = {"name": f"Team {team_h}", "short": str(team_h)[:3].upper()}
            if team_a not in teams and isinstance(team_a, (int, float)):
                teams[int(team_a)] = {"name": f"Team {team_a}", "short": str(team_a)[:3].upper()}
            rows.append({
                "GW": int(f.get("event") or 0),
                "Home": teams.get(team_h, {}).get("short", ""),
                "Away": teams.get(team_a, {}).get("short", ""),
                "HomeName": teams.get(team_h, {}).get("name", ""),
                "AwayName": teams.get(team_a, {}).get("name", ""),
                "Kickoff": f.get("kickoff_time")
            })
        except Exception:
            continue

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["GW", "Kickoff"], na_position="last").reset_index(drop=True)
    team_list = sorted({v["short"] for v in teams.values() if v.get("short")})
    return df, team_list, teams

# ---------------------
# Load data
# ---------------------
with st.spinner("Loading FPL data..."):
    df, team_codes, teams_full = load_fpl_data()

if df.empty or len(team_codes) == 0 or not teams_full:
    st.error("Unable to load Fantasy Premier League fixtures/team list.")
    st.stop()

# ---------------------
# Default difficulty values
# ---------------------
DEFAULT_VALUES = {t: {"Home": 1250, "Away": 1350} for t in team_codes}

# ---------------------
# Initialize from browser localStorage
# ---------------------
if "difficulties" not in st.session_state:
    data = local_store.get()

    if data is not None:
        try:
            df_local = pd.DataFrame.from_dict(data)
            df_local.index.name = "Team"
            st.session_state["difficulties"] = df_local
        except Exception:
            st.session_state["difficulties"] = pd.DataFrame({
                "Team": team_codes,
                "Home": [DEFAULT_VALUES[t]["Home"] for t in team_codes],
                "Away": [DEFAULT_VALUES[t]["Away"] for t in team_codes],
            }).set_index("Team")
    else:
        st.session_state["difficulties"] = pd.DataFrame({
            "Team": team_codes,
            "Home": [DEFAULT_VALUES[t]["Home"] for t in team_codes],
            "Away": [DEFAULT_VALUES[t]["Away"] for t in team_codes],
        }).set_index("Team")

def ensure_difficulties_cover_teams():
    df_cur = st.session_state["difficulties"]
    for t in team_codes:
        if t not in df_cur.index:
            df_cur.loc[t] = [
                DEFAULT_VALUES[t]["Home"],
                DEFAULT_VALUES[t]["Away"]
            ]
    st.session_state["difficulties"] = df_cur.reindex(team_codes)

ensure_difficulties_cover_teams()

# ---------------------
# Sidebar controls
# ---------------------
with st.sidebar:

    min_gw, max_gw = int(df["GW"].min()), int(df["GW"].max())

    gw_start, gw_end = st.slider(
        "Select GW Range",
        min_value=min_gw,
        max_value=max_gw,
        value=(min(min_gw+11, max_gw), min(min_gw+15, max_gw))
    )

    range_gws = list(range(gw_start, gw_end + 1))
    exclusion_choice = st.selectbox(
        "Exclude a GW (optional / Free Hit)",
        ["None"] + [str(g) for g in range_gws],
        index=0
    )
    excluded_gw = None if exclusion_choice == "None" else int(exclusion_choice)

    st.markdown("---")
    st.header("Controls")

    st.write("Edits auto-save to your browser (per user).")

    # Editable table
    edited = st.data_editor(st.session_state["difficulties"], use_container_width=True)
    if not edited.equals(st.session_state["difficulties"]):
        edited_copy = edited.copy()
        edited_copy.index.name = "Team"
        st.session_state["difficulties"] = edited_copy
        local_store.set(edited_copy.to_dict())  # SAVE
        st.experimental_rerun()

    st.markdown("---")

    # Sliders
    with st.expander("Difficulty Sliders (adjust + Apply)"):

        for t in team_codes:
            kh = f"slider_home_{t}"
            ka = f"slider_away_{t}"
            if kh not in st.session_state:
                st.session_state[kh] = int(st.session_state["difficulties"].loc[t, "Home"])
            if ka not in st.session_state:
                st.session_state[ka] = int(st.session_state["difficulties"].loc[t, "Away"])

        for t in team_codes:
            c1, c2 = st.columns([1,1])
            with c1:
                st.slider(f"{t} Home", 500, 2000,
                          st.session_state[f"slider_home_{t}"],
                          key=f"slider_home_{t}")
            with c2:
                st.slider(f"{t} Away", 500, 2000,
                          st.session_state[f"slider_away_{t}"],
                          key=f"slider_away_{t}")

        if st.button("Apply sliders"):
            new_df = pd.DataFrame({
                "Team": team_codes,
                "Home": [st.session_state[f"slider_home_{t}"] for t in team_codes],
                "Away": [st.session_state[f"slider_away_{t}"] for t in team_codes],
            }).set_index("Team")

            st.session_state["difficulties"] = new_df
            local_store.set(new_df.to_dict())   # SAVE
            st.experimental_rerun()

# ---------------------
# ... the rest of your script remains unchanged ...
# (YOUR ORIGINAL CALCULATIONS, GRID, AND OUTPUT)
# ---------------------
