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
from streamlit_browser_storage import BrowserStorage

st.set_page_config(layout="wide", page_title="FPL Season Ticker v14")

# ---------------------
# Browser Local Storage
# ---------------------
local_store = BrowserStorage(key="user_difficulties_v14")

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
        # SAVE TO LOCAL STORAGE
        local_store.set(edited_copy.to_dict())
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
                st.slider(f"{t} Home", 500, 2000, st.session_state[f"slider_home_{t}"], key=f"slider_home_{t}")
            with c2:
                st.slider(f"{t} Away", 500, 2000, st.session_state[f"slider_away_{t}"], key=f"slider_away_{t}")

        if st.button("Apply sliders"):
            new_df = pd.DataFrame({
                "Team": team_codes,
                "Home": [st.session_state[f"slider_home_{t}"] for t in team_codes],
                "Away": [st.session_state[f"slider_away_{t}"] for t in team_codes],
            }).set_index("Team")

            st.session_state["difficulties"] = new_df
            local_store.set(new_df.to_dict())   # SAVE TO LOCAL STORAGE
            st.experimental_rerun()

# ---------------------
# Calculations
# ---------------------
if excluded_gw is None:
    subset_for_calcs = df[(df["GW"] >= gw_start) & (df["GW"] <= gw_end)]
else:
    subset_for_calcs = df[(df["GW"] >= gw_start) & (df["GW"] <= gw_end) & (df["GW"] != excluded_gw)]

short_to_full = {v["short"]: v["name"] for v in teams_full.values() if v.get("short")}
missing_opponents = set()

team_stats = []
for team in team_codes:
    total = 0.0
    matches = 0
    cell_map = []

    for _, r in subset_for_calcs.iterrows():
        try:
            if r["Home"] == team:
                opp = r["Away"]
                val = st.session_state["difficulties"].loc[opp, "Home"]
                total += float(val)
                matches += 1
                cell_map.append((r["GW"], opp, "H", val))

            elif r["Away"] == team:
                opp = r["Home"]
                val = st.session_state["difficulties"].loc[opp, "Away"]
                total += float(val)
                matches += 1
                cell_map.append((r["GW"], opp, "A", val))
        except Exception:
            missing_opponents.add(opp)

    avg = total / matches if matches else 0.0
    team_stats.append({
        "Team": team,
        "Name": short_to_full.get(team, team),
        "Total": total,
        "Avg": avg,
        "Matches": matches,
        "Cells": cell_map
    })

stats_df = pd.DataFrame(team_stats).sort_values("Total").reset_index(drop=True)
sorted_teams = stats_df["Team"].tolist()

# ---------------------
# Build the fixture grid
# ---------------------
full_range_df = df[(df["GW"] >= gw_start) & (df["GW"] <= gw_end)]
gw_list = list(range(gw_start, gw_end + 1))

grid_text = pd.DataFrame("", index=sorted_teams, columns=[f"GW{g}" for g in gw_list])
grid_vals = pd.DataFrame(np.nan, index=sorted_teams, columns=[f"GW{g}" for g in gw_list])

for team in sorted_teams:
    for gw in gw_list:
        matches_gw = full_range_df[full_range_df["GW"] == gw]
        parts = []
        vals = []
        for _, row in matches_gw.iterrows():
            if row["Home"] == team:
                opp = row["Away"]
                parts.append(str(opp).upper())
                vals.append(float(st.session_state["difficulties"].loc[opp, "Home"]))
            elif row["Away"] == team:
                opp = row["Home"]
                parts.append(str(opp).lower())
                vals.append(float(st.session_state["difficulties"].loc[opp, "Away"]))

        if parts:
            grid_text.loc[team, f"GW{gw}"] = ", ".join(parts)
            grid_vals.loc[team, f"GW{gw}"] = np.nanmean(vals)
        else:
            grid_text.loc[team, f"GW{gw}"] = ""
            grid_vals.loc[team, f"GW{gw}"] = np.nan

# ---------------------
# UI Layout
# ---------------------
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader(f"Sorted Teams (GW{gw_start} → GW{gw_end}"
                 + (f", excluding GW{excluded_gw})" if excluded_gw else ")"))

    display = stats_df[["Team", "Name", "Total", "Avg", "Matches"]].copy()
    display["Avg"] = display["Avg"].round(1)

    num_rows = max(1, display.shape[0])
    height_display = int(max(300, min(1400, num_rows * 36 + 40)))
    st.dataframe(display, height=height_display, use_container_width=True, hide_index=True)

    # Allow CSV download
    if st.button("Download sorted CSV"):
        st.download_button(
            "Download sorted_ticker.csv",
            data=display.to_csv(index=False).encode("utf-8"),
            file_name="sorted_ticker.csv"
        )

with col_right:
    st.subheader("Fixture Grid")
    cmap = cm.get_cmap("RdYlGn_r")

    try:
        vmin = np.nanmin(grid_vals.values)
        vmax = np.nanmax(grid_vals.values)
        if np.isnan(vmin) or np.isnan(vmax) or vmin == vmax:
            vmin, vmax = 500, 2000
    except Exception:
        vmin, vmax = 500, 2000

    norm = colors.Normalize(vmin=vmin, vmax=vmax)

    def style_cell(val):
        if pd.isna(val):
            return ""
        col = colors.to_hex(cmap(norm(val)))
        return f"background-color:{col};color:black;"

    styles = pd.DataFrame("", index=grid_text.index, columns=grid_text.columns)
    for r in grid_text.index:
        for c in grid_text.columns:
            gw_num = int(c.replace("GW", ""))
            if excluded_gw and gw_num == excluded_gw:
                styles.loc[r, c] = "background-color:#e6e6e6;color:#888888;"
            else:
                v = grid_vals.loc[r, c]
                if not pd.isna(v):
                    styles.loc[r, c] = style_cell(v)

    styled = grid_text.style.apply(lambda row: styles.loc[row.name], axis=1)
    st.dataframe(styled, height=800, use_container_width=True)

# Footer
st.markdown("""
---
### Notes about excluded GW
- Excluded GW is hidden from totals/averages.
- Still visible (but greyed) in the grid.
- You can only exclude one GW at a time.
""")
