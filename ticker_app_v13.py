# ticker_app_v14.py
# v14: per-user persistence using Browser LocalStorage
# - Removed disk saving
# - Difficulty data now saved per user/device via JS localStorage
# - Everything else identical to v13

import os
import streamlit as st
import pandas as pd
import numpy as np
import requests
from matplotlib import cm, colors
from typing import Tuple, Dict, List

st.set_page_config(layout="wide", page_title="FPL Season Ticker v14")

# ---------------------------
# Browser-storage helpers
# ---------------------------
import json

def save_to_browser(key: str, value):
    """Save python object to browser localStorage."""
    try:
        ser = json.dumps(value)
    except Exception:
        ser = "{}"
    js = f"localStorage.setItem('{key}', `{ser}`);"
    st.js_eval(js)

def load_from_browser(key: str):
    """Load python object from browser localStorage."""
    js = f"localStorage.getItem('{key}')"
    raw = st.js_eval(js)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

# ---------------------------
# FPL API endpoints
# ---------------------------
FIX_API = "https://fantasy.premierleague.com/api/fixtures/"
BOOT_API = "https://fantasy.premierleague.com/api/bootstrap-static/"

# ---------------------------
# Utility: load fpl data robustly
# ---------------------------
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
            if isinstance(f.get("team_h"), (int, float)):
                ids.add(int(f["team_h"]))
            if isinstance(f.get("team_a"), (int, float)):
                ids.add(int(f["team_a"]))
        for tid in ids:
            teams[int(tid)] = {"name": f"Team {tid}", "short": str(tid)[:3].upper()}

    rows = []
    for f in fixtures:
        try:
            if f.get("event") is None:
                continue
            team_h = f.get("team_h")
            team_a = f.get("team_a")

            if team_h not in teams:
                teams[int(team_h)] = {"name": f"Team {team_h}", "short": str(team_h)[:3].upper()}
            if team_a not in teams:
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

# ---------------------------
# Load FPL data
# ---------------------------
with st.spinner("Loading FPL data…"):
    df, team_codes, teams_full = load_fpl_data()

if df.empty or len(team_codes) == 0 or not teams_full:
    st.error(
        "Unable to load Fantasy Premier League fixtures/team list right now."
    )
    st.stop()

# ---------------------------
# Defaults
# ---------------------------
DEFAULT_VALUES = {t: {"Home": 1250, "Away": 1350} for t in team_codes}

# ---------------------------
# Initialize per-user difficulties
# ---------------------------
if "difficulties" not in st.session_state:

    # ---- Try loading from browser ----
    loaded = load_from_browser("user_difficulties")

    if isinstance(loaded, dict) and len(loaded) > 0:
        try:
            df_loaded = pd.DataFrame(loaded).T
            df_loaded.index.name = "Team"
            df_loaded = df_loaded[["Home", "Away"]].astype(float)
            st.session_state["difficulties"] = df_loaded
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
    changed = False
    for t in team_codes:
        if t not in df_cur.index:
            df_cur.loc[t] = [DEFAULT_VALUES[t]["Home"], DEFAULT_VALUES[t]["Away"]]
            changed = True
    if changed:
        st.session_state["difficulties"] = df_cur.reindex(team_codes)

ensure_difficulties_cover_teams()

# ---------------------------
# Sidebar
# ---------------------------
with st.sidebar:
    min_gw, max_gw = int(df["GW"].min()), int(df["GW"].max())
    gw_start, gw_end = st.slider(
        "Select GW Range", min_value=min_gw, max_value=max_gw,
        value=(min(min_gw+11, max_gw), min(min_gw+15, max_gw))
    )

    range_gws = list(range(gw_start, gw_end + 1))
    if range_gws:
        opts = ["None"] + [str(g) for g in range_gws]
        ex_choice = st.selectbox("Exclude a GW (optional)", opts)
        excluded_gw = None if ex_choice == "None" else int(ex_choice)
    else:
        excluded_gw = None

    st.markdown("---")
    st.header("Controls")
    st.write("Edit difficulties manually or via sliders.")

    # Editable grid
    edited = st.data_editor(st.session_state["difficulties"], use_container_width=True)
    if not edited.equals(st.session_state["difficulties"]):
        edited_copy = edited.copy()
        edited_copy.index.name = "Team"
        st.session_state["difficulties"] = edited_copy

        # Save to browser
        save_to_browser("user_difficulties", edited_copy.to_dict())

        st.success("Saved to your browser!")

    st.markdown("---")
    with st.expander("Difficulty Sliders"):
        for t in team_codes:
            if f"h_{t}" not in st.session_state:
                st.session_state[f"h_{t}"] = int(st.session_state["difficulties"].loc[t, "Home"])
            if f"a_{t}" not in st.session_state:
                st.session_state[f"a_{t}"] = int(st.session_state["difficulties"].loc[t, "Away"])

        for t in team_codes:
            c1, c2 = st.columns([1,1])
            with c1:
                st.slider(f"{t} Home", 500, 2000, st.session_state[f"h_{t}"], key=f"h_{t}")
            with c2:
                st.slider(f"{t} Away", 500, 2000, st.session_state[f"a_{t}"], key=f"a_{t}")

        if st.button("Apply"):
            new_df = pd.DataFrame({
                "Team": team_codes,
                "Home": [st.session_state[f"h_{t}"] for t in team_codes],
                "Away": [st.session_state[f"a_{t}"] for t in team_codes],
            }).set_index("Team")

            st.session_state["difficulties"] = new_df
            save_to_browser("user_difficulties", new_df.to_dict())
            st.success("Applied and saved!")

    st.markdown("---")
    if st.button("Download difficulties CSV"):
        csv_bytes = st.session_state["difficulties"].to_csv().encode("utf-8")
        st.download_button("Download", csv_bytes, "saved_difficulties.csv")

    uploaded = st.file_uploader("Import difficulties CSV", type=["csv"])
    if uploaded:
        try:
            imp = pd.read_csv(uploaded).set_index("Team")
            imp["Home"] = pd.to_numeric(imp["Home"], errors="coerce")
            imp["Away"] = pd.to_numeric(imp["Away"], errors="coerce")

            st.session_state["difficulties"] = imp
            save_to_browser("user_difficulties", imp.to_dict())
            st.success("Imported & saved!")
        except Exception as e:
            st.error(f"Import failed: {e}")

# ---------------------------
# Compute fixture stats
# ---------------------------
if excluded_gw is None:
    subset = df[(df["GW"] >= gw_start) & (df["GW"] <= gw_end)]
else:
    subset = df[(df["GW"] >= gw_start) & (df["GW"] <= gw_end) & (df["GW"] != excluded_gw)]

short_to_full = {v["short"]: v["name"] for v in teams_full.values() if v.get("short")}
missing = set()
team_stats = []

for team in team_codes:
    total = 0.0; matches = 0; cells = []
    for _, r in subset.iterrows():
        try:
            if r["Home"] == team:
                opp = r["Away"]
                val = st.session_state["difficulties"].loc[opp, "Home"]
                total += val; matches += 1
                cells.append((r["GW"], opp, "H", val))
            elif r["Away"] == team:
                opp = r["Home"]
                val = st.session_state["difficulties"].loc[opp, "Away"]
                total += val; matches += 1
                cells.append((r["GW"], opp, "A", val))
        except Exception:
            missing.add(opp)
    avg = total/matches if matches else 0
    team_stats.append({
        "Team": team,
        "Name": short_to_full.get(team, team),
        "Total": total,
        "Avg": avg,
        "Matches": matches,
        "Cells": cells
    })

stats_df = pd.DataFrame(team_stats).sort_values("Total")

# ---------------------------
# Grid build
# ---------------------------
full_range_df = df[(df["GW"] >= gw_start) & (df["GW"] <= gw_end)]
gw_list = list(range(gw_start, gw_end+1))

grid_text = pd.DataFrame("", index=stats_df["Team"], columns=[f"GW{g}" for g in gw_list])
grid_vals = pd.DataFrame(np.nan, index=stats_df["Team"], columns=[f"GW{g}" for g in gw_list])

for t in stats_df["Team"]:
    for gw in gw_list:
        matches_gw = full_range_df[full_range_df["GW"] == gw]
        parts = []; vals = []
        for _, row in matches_gw.iterrows():
            try:
                if row["Home"] == t:
                    opp = row["Away"]; parts.append(opp.upper())
                    vals.append(st.session_state["difficulties"].loc[opp, "Home"])
                elif row["Away"] == t:
                    opp = row["Home"]; parts.append(opp.lower())
                    vals.append(st.session_state["difficulties"].loc[opp, "Away"])
            except:
                continue
        if parts:
            grid_text.loc[t, f"GW{gw}"] = ", ".join(parts)
            if vals:
                grid_vals.loc[t, f"GW{gw}"] = float(np.mean(vals))

# ---------------------------
# Layout: left table + right grid
# ---------------------------
col1, col2 = st.columns([1,2])

with col1:
    st.subheader(f"Sorted Teams (GW{gw_start}–GW{gw_end}" + (f", excl GW{excluded_gw})" if excluded_gw else ")"))
    display = stats_df[["Team", "Name", "Total", "Avg", "Matches"]].copy()
    display["Avg"] = display["Avg"].round(1)
    rows = max(1, display.shape[0])
    st.dataframe(display, height=min(1400, 36*rows + 50), use_container_width=True, hide_index=True)

with col2:
    st.subheader("Fixture Grid")
    cmap = cm.get_cmap("RdYlGn_r")
    try:
        vmin = np.nanmin(grid_vals.values); vmax = np.nanmax(grid_vals.values)
        if np.isnan(vmin) or vmin == vmax:
            vmin, vmax = 500, 2000
    except:
        vmin, vmax = 500, 2000
    norm = colors.Normalize(vmin, vmax)

    def style_val(v):
        if pd.isna(v): return ""
        col = colors.to_hex(cmap(norm(v)))
        return f"background-color:{col};color:black;"

    styles = pd.DataFrame("", index=grid_text.index, columns=grid_text.columns)
    for r in grid_text.index:
        for c in grid_text.columns:
            gw_num = int(c.replace("GW",""))
            v = grid_vals.loc[r,c]
            if excluded_gw and gw_num == excluded_gw:
                styles.loc[r,c] = "background-color:#e6e6e6;color:#888;"
            else:
                styles.loc[r,c] = style_val(v)

    styled = grid_text.style.apply(lambda row: styles.loc[row.name], axis=1)
    st.dataframe(styled, height=800, use_container_width=True)

st.markdown("""
---
### Notes
- Difficulties are now stored **privately in your browser**.
- No user accounts needed.  
- Settings persist until you clear browser data.  
""")
