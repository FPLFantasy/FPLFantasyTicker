# ticker_app_v14.py — Pure Browser Local Storage Version (FINAL WORKING PATCH)
# ---------------------------------------------------------------------------
# - Uses streamlit-local-storage (NOT streamlit_browser_storage)
# - Each user keeps their own Home/Away difficulties in browser localStorage
# - No server storage, no volumes, no CSV, no env vars

import streamlit as st
import pandas as pd
import numpy as np
import requests
from typing import Tuple, Dict, List
from matplotlib import cm, colors

# ✅ WORKING LOCAL STORAGE LIBRARY
from streamlit_local_storage import LocalStorage

st.set_page_config(layout="wide", page_title="FPL Season Ticker v14")

# ---------------------
# Browser Local Storage
# ---------------------
localS = LocalStorage()
KEY = "user_difficulties_v14"  # each user keeps their own data

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

    if not teams and isinstance(fixtures, list):
        ids = set()
        for f in fixtures:
            try:
                if isinstance(f.get("team_h"), (int, float)):
                    ids.add(int(f["team_h"]))
                if isinstance(f.get("team_a"), (int, float)):
                    ids.add(int(f["team_a"]))
            except:
                continue
        for tid in ids:
            teams[tid] = {"name": f"Team {tid}", "short": str(tid)[:3].upper()}

    rows = []
    for f in fixtures:
        try:
            if f.get("event") is None:
                continue
            team_h = f.get("team_h")
            team_a = f.get("team_a")
            if team_h not in teams:
                teams[team_h] = {"name": f"Team {team_h}", "short": str(team_h)[:3].upper()}
            if team_a not in teams:
                teams[team_a] = {"name": f"Team {team_a}", "short": str(team_a)[:3].upper()}

            rows.append({
                "GW": int(f.get("event") or 0),
                "Home": teams.get(team_h, {}).get("short", ""),
                "Away": teams.get(team_a, {}).get("short", ""),
                "HomeName": teams.get(team_h, {}).get("name", ""),
                "AwayName": teams.get(team_a, {}).get("name", ""),
                "Kickoff": f.get("kickoff_time")
            })
        except:
            continue

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["GW", "Kickoff"], na_position="last").reset_index(drop=True)

    team_list = sorted({v["short"] for v in teams.values() if v.get("short")})
    return df, team_list, teams

# ---------------------
# Load FPL fixture data
# ---------------------
with st.spinner("Loading FPL data..."):
    df, team_codes, teams_full = load_fpl_data()

if df.empty:
    st.error("Unable to load Fantasy Premier League fixtures.")
    st.stop()

# ---------------------
# Default difficulty table
# ---------------------
DEFAULT_VALUES = {t: {"Home": 1250, "Away": 1350} for t in team_codes}

DEFAULT_DF = pd.DataFrame({
    "Team": team_codes,
    "Home": [DEFAULT_VALUES[t]["Home"] for t in team_codes],
    "Away": [DEFAULT_VALUES[t]["Away"] for t in team_codes]
}).set_index("Team")

# ---------------------
# Load difficulties from localStorage → into session_state
# ---------------------
if "difficulties" not in st.session_state:
    saved = localS.getItem(KEY)

    if saved is not None:
        try:
            df_local = pd.DataFrame.from_dict(saved)
            df_local.index.name = "Team"
            st.session_state["difficulties"] = df_local
        except:
            st.session_state["difficulties"] = DEFAULT_DF.copy()
    else:
        st.session_state["difficulties"] = DEFAULT_DF.copy()

# Ensure all teams exist
df_cur = st.session_state["difficulties"]
for t in team_codes:
    if t not in df_cur.index:
        df_cur.loc[t] = DEFAULT_VALUES[t]
st.session_state["difficulties"] = df_cur.reindex(team_codes)

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

    exclude_choice = st.selectbox(
        "Exclude a GW (optional / Free Hit)",
        ["None"] + [str(g) for g in range_gws],
        index=0
    )
    excluded_gw = None if exclude_choice == "None" else int(exclude_choice)

    st.markdown("---")
    st.header("Controls")
    st.write("Edits auto-save to your browser (per user).")

    edited = st.data_editor(st.session_state["difficulties"], use_container_width=True)
    if not edited.equals(st.session_state["difficulties"]):
        edited_copy = edited.copy()
        edited_copy.index.name = "Team"
        st.session_state["difficulties"] = edited_copy
        localS.setItem(KEY, edited_copy.to_dict())  # SAVE
        st.rerun()


    st.markdown("---")

    with st.expander("Difficulty Sliders (adjust + Apply)"):

        for t in team_codes:
            h_key = f"slider_home_{t}"
            a_key = f"slider_away_{t}"

            if h_key not in st.session_state:
                st.session_state[h_key] = int(df_cur.loc[t, "Home"])
            if a_key not in st.session_state:
                st.session_state[a_key] = int(df_cur.loc[t, "Away"])

        for t in team_codes:
            c1, c2 = st.columns(2)
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
            localS.setItem(KEY, new_df.to_dict())   # SAVE
            st.rerun()


# ---------------------
# ... your existing ticker calculation + display code goes here ...
# (unchanged, since storage logic is complete)
# ---------------------
