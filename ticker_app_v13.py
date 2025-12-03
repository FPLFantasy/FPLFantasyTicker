

import streamlit as st
import pandas as pd
import numpy as np
import requests
from matplotlib import cm, colors
from typing import Tuple, Dict, List

# Local storage lib (must be in requirements.txt)
from streamlit_local_storage import LocalStorage

st.set_page_config(layout="wide", page_title="FPL Fantasy Ticker")

# ---------------------
# Browser local storage (per-user)
# ---------------------
localS = LocalStorage() # This line ensures the component is initialized and begins sync
# localS.load_all() # <-- ❌ REMOVED: This was the source of the 'AttributeError'
LOCAL_KEY = "saved_difficulties_v13" # key in browser localStorage

# ---------------------
# API endpoints
# ---------------------
FIX_API = "https://fantasy.premierleague.com/api/fixtures/"
BOOT_API = "https://fantasy.premierleague.com/api/bootstrap-static/"

# ---------------------
# Utility: load FPL data (robust)
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
                "Home": teams.get(f.get("team_h"), {}).get("short", "") or "",
                "Away": teams.get(f.get("team_a"), {}).get("short", "") or "",
                "HomeName": teams.get(f.get("team_h"), {}).get("name", "") or "",
                "AwayName": teams.get(f.get("team_a"), {}).get("name", "") or "",
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
# Loading FPL data with spinner and friendly errors
# ---------------------
with st.spinner("Loading FPL data..."):
    df, team_codes, teams_full = load_fpl_data()

if df.empty or len(team_codes) == 0 or not teams_full:
    st.error(
        "Unable to load Fantasy Premier League fixtures/team list right now. "
        "This can happen during preseason or if the FPL API is unreachable."
    )
    st.info(
        "If you deployed to Railway, ensure outbound HTTP to fantasy.premierleague.com is allowed. Try again later."
    )
    st.stop()

# ---------------------
# Defaults (CUSTOMIZABLE)
# NOTE: Edit CUSTOM_DEFAULTS below to set the initial difficulties for each team.
# Keys must be the FPL short codes (e.g., 'ARS', 'AVL').
# ---------------------
CUSTOM_DEFAULTS = {
    # --- START EDITING YOUR CUSTOM DEFAULTS HERE ---
    "ARS": {"Home": 1750, "Away": 1950},  # Example: Arsenal (Strong)
    "AVL": {"Home": 1100, "Away": 1250},  # Example: Aston Villa (Moderate/Weak)
    "BHA": {"Home": 1200, "Away": 1300},
    "BOU": {"Home": 1100, "Away": 1250},
    "BRE": {"Home": 1050, "Away": 1200},
    "BUR": {"Home": 900, "Away": 950},
    "CHE": {"Home": 1450, "Away": 1600},
    "CRY": {"Home": 1150, "Away": 1300},
    "EVE": {"Home": 1000, "Away": 1100},
    "FUL": {"Home": 1050, "Away": 1150},
    "LEE": {"Home": 1000, "Away": 1050},  # Example: Arsenal (Strong)
    "LIV": {"Home": 1400, "Away": 1500},  # Example: Aston Villa (Moderate/Weak)
    "MCI": {"Home": 1450, "Away": 1600},
    "MUN": {"Home": 1200, "Away": 1300},
    "NEW": {"Home": 1150, "Away": 1300},
    "NFO": {"Home": 1050, "Away": 1100},
    "SUN": {"Home": 1000, "Away": 1150},
    "TOT": {"Home": 1000, "Away": 1150},
    "WHU": {"Home": 900, "Away": 1000},
    "WOL": {"Home": 750, "Away": 800},
    # ...
    # --- END EDITING YOUR CUSTOM DEFAULTS HERE ---
}

# Generic fallback values for any team not in the custom list
GENERIC_HOME_DEFAULT = 1250
GENERIC_AWAY_DEFAULT = 1350

# Construct the final DEFAULT_VALUES dictionary using custom values or fallback
DEFAULT_VALUES = {}
for t in team_codes:
    if t in CUSTOM_DEFAULTS:
        # Use your custom, specified values
        DEFAULT_VALUES[t] = CUSTOM_DEFAULTS[t]
    else:
        # Use the generic fallback for any team you didn't specify
        DEFAULT_VALUES[t] = {"Home": GENERIC_HOME_DEFAULT, "Away": GENERIC_AWAY_DEFAULT}

# ---------------------
# Local-storage based persistence helpers (replace disk IO)
# Keep function names so the rest of your script is unchanged.
# ---------------------
def load_saved_difficulties_from_disk() -> pd.DataFrame:
    """
    NOTE: Keep original function name for compatibility.
    Now loads per-user saved difficulties from browser localStorage.
    Returns DataFrame or None.
    """
    try:
        saved = localS.getItem(LOCAL_KEY)
        if saved is None:
            return None
        # saved expected to be a dict with orient='index'
        try:
            df_saved = pd.DataFrame.from_dict(saved, orient="index")
            # ensure columns Home/Away exist
            if "Home" in df_saved.columns and "Away" in df_saved.columns:
                df_saved["Home"] = pd.to_numeric(df_saved["Home"], errors="coerce")
                df_saved["Away"] = pd.to_numeric(df_saved["Away"], errors="coerce")
                # ensure index name is Team if not present
                if df_saved.index.name is None:
                    df_saved.index.name = "Team"
                return df_saved
            else:
                # malformed saved object
                return None
        except Exception:
            return None
    except Exception:
        return None

def atomic_save_difficulties(df_to_save: pd.DataFrame):
    """
    NOTE: Keep original function name for compatibility.
    Now saves to browser localStorage for the current user.
    """
    try:
        df_copy = df_to_save.copy()
        # ensure index name is Team
        df_copy.index.name = "Team"
        # store with orient='index' so index keys -> row dicts
        localS.setItem(LOCAL_KEY, df_copy.to_dict(orient="index"))
        # show success to the user
        st.success("Saved difficulties to your browser (local storage).")
    except Exception as e:
        st.error(f"Failed to save difficulties to browser local storage: {e}")

# ---------------------
# Initialize difficulties in session_state (so UI is reactive)
# ---------------------
if "difficulties" not in st.session_state:
    saved = load_saved_difficulties_from_disk()
    if isinstance(saved, pd.DataFrame):
        st.session_state["difficulties"] = saved.copy()
    else:
        st.session_state["difficulties"] = pd.DataFrame({
            "Team": team_codes,
            # Use the values from the DEFAULT_VALUES dictionary constructed above
            "Home": [DEFAULT_VALUES.get(t, {}).get("Home", 1250) for t in team_codes],
            "Away": [DEFAULT_VALUES.get(t, {}).get("Away", 1350) for t in team_codes],
        }).set_index("Team")

def ensure_difficulties_cover_teams():
    df_cur = st.session_state["difficulties"]
    for t in team_codes:
        if t not in df_cur.index:
            # Use the values from the DEFAULT_VALUES dictionary constructed above
            df_cur.loc[t] = [DEFAULT_VALUES.get(t, {}).get("Home", 1250),
                             DEFAULT_VALUES.get(t, {}).get("Away", 1350)]
    st.session_state["difficulties"] = df_cur.reindex(team_codes)

ensure_difficulties_cover_teams()

# ---------------------
# Sidebar: GW selection, difficulty editor, sliders
# ---------------------
with st.sidebar:
    if not df.empty:
        min_gw, max_gw = int(df["GW"].min()), int(df["GW"].max())
    else:
        min_gw, max_gw = 1, 38
    gw_start, gw_end = st.slider(
        "Select GW Range",
        min_value=min_gw,
        max_value=max_gw,
        value=(min(min_gw+11, max_gw), min(min_gw+15, max_gw))
    )

    range_gws = list(range(gw_start, gw_end + 1))
    if range_gws:
        exclude_options = ["None"] + [str(g) for g in range_gws]
        exclusion_choice = st.selectbox("Exclude a GW from the selected range (optional/FreeHit Week)", exclude_options, index=0)
        excluded_gw = None if exclusion_choice == "None" else int(exclusion_choice)
        if excluded_gw is not None:
            st.info(f"GW{excluded_gw} will be excluded from totals/avg calculations (it will remain visible in the grid).")
    else:
        excluded_gw = None

    st.markdown("---")
    st.header("Controls")

    st.write("**Edit difficulties (In the table or sliders below).**")
    st.write("- **Home** = Difficulty of opponent visiting you (you're HOME)  \n- **Away** = Difficulty when you travel (you're AWAY)")

    # Editable table
    edited = st.data_editor(st.session_state["difficulties"], use_container_width=True)
    if not edited.equals(st.session_state["difficulties"]):
        with st.spinner("Saving edited difficulties..."):
            edited_copy = edited.copy()
            edited_copy.index.name = "Team"
            st.session_state["difficulties"] = edited_copy
            atomic_save_difficulties(edited_copy)
            # ensure UI reflects saved changes without manual refresh
            st.rerun()

    with st.expander("Difficulty Sliders (Adjust & Apply)"):
        st.markdown("Use sliders to visually adjust Home/Away. Click **Apply sliders** to commit changes.")

        for t in team_codes:
            kh = f"slider_home_{t}"
            ka = f"slider_away_{t}"
            if kh not in st.session_state:
                try:
                    st.session_state[kh] = int(st.session_state["difficulties"].loc[t, "Home"])
                except Exception:
                    st.session_state[kh] = DEFAULT_VALUES[t]["Home"]
            if ka not in st.session_state:
                try:
                    st.session_state[ka] = int(st.session_state["difficulties"].loc[t, "Away"])
                except Exception:
                    st.session_state[ka] = DEFAULT_VALUES[t]["Away"]

        for t in team_codes:
            c1, c2 = st.columns([1,1])
            with c1:
                st.slider(f"{t} Home", min_value=500, max_value=2000, value=st.session_state[f"slider_home_{t}"], key=f"slider_home_{t}")
            with c2:
                st.slider(f"{t} Away", min_value=500, max_value=2000, value=st.session_state[f"slider_away_{t}"], key=f"slider_away_{t}")

        if st.button("Apply sliders (save & apply)"):
            with st.spinner("Applying sliders and saving..."):
                try:
                    new_df = pd.DataFrame({
                        "Team": team_codes,
                        "Home": [st.session_state[f"slider_home_{t}"] for t in team_codes],
                        "Away": [st.session_state[f"slider_away_{t}"] for t in team_codes],
                    }).set_index("Team")
                    st.session_state["difficulties"] = new_df
                    atomic_save_difficulties(new_df)
                    # reflect changes immediately
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to apply/save sliders: {e}")

    st.markdown("---")
    if st.button("Download difficulties (CSV)"):
        csv_bytes = st.session_state["difficulties"].to_csv(index=True).encode("utf-8")
        st.download_button("Download saved_difficulties.csv", data=csv_bytes, file_name="saved_difficulties.csv")
    uploaded = st.file_uploader("Import difficulties CSV (will overwrite)", type=["csv"])
    if uploaded is not None:
        try:
            imported = pd.read_csv(uploaded).set_index("Team")
            imported["Home"] = pd.to_numeric(imported["Home"], errors="coerce")
            imported["Away"] = pd.to_numeric(imported["Away"], errors="coerce")
            st.session_state["difficulties"] = imported
            atomic_save_difficulties(imported)
            st.success("Imported and saved difficulties (to your browser).")
            st.rerun()
        except Exception as e:
            st.error(f"Import failed: {e}")

# ---------------------
# Computations: totals/avg per team (use selected GW range, excluding excluded_gw)
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
                if opp in st.session_state["difficulties"].index:
                    val = st.session_state["difficulties"].loc[opp, "Home"]
                else:
                    val = DEFAULT_VALUES.get(opp, {}).get("Home", np.nan)
                    if pd.isna(val):
                        missing_opponents.add(opp)
                if not pd.isna(val):
                    total += float(val)
                    matches += 1
                cell_map.append((r["GW"], opp, "H", val))
            elif r["Away"] == team:
                opp = r["Home"]
                if opp in st.session_state["difficulties"].index:
                    val = st.session_state["difficulties"].loc[opp, "Away"]
                else:
                    val = DEFAULT_VALUES.get(opp, {}).get("Away", np.nan)
                    if pd.isna(val):
                        missing_opponents.add(opp)
                if not pd.isna(val):
                    total += float(val)
                    matches += 1
                cell_map.append((r["GW"], opp, "A", val))
        except Exception:
            missing_opponents.add(r.get("Home") or r.get("Away") or "unknown")
    avg = total / matches if matches > 0 else 0.0
    team_full_name = short_to_full.get(team, team)
    team_stats.append({
        "Team": team,
        "Name": team_full_name,
        "Total": total,
        "Avg": avg,
        "Matches": matches,
        "Cells": cell_map
    })

stats_df = pd.DataFrame(team_stats).sort_values("Total").reset_index(drop=True)
sorted_teams = stats_df["Team"].tolist()

if missing_opponents:
    st.warning(
        "Some opponents lacked difficulty values or full FPL bootstrap mapping. "
        "Defaults/NaNs were used when necessary. "
        "Example missing: " + ", ".join(sorted(map(str, list(missing_opponents)[:10]))) +
        ("..." if len(missing_opponents) > 10 else "")
    )

# ---------------------
# Build fixture grid view
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
            try:
                if row["Home"] == team:
                    opp = row["Away"]
                    parts.append(str(opp).upper())
                    if opp in st.session_state["difficulties"].index:
                        v = st.session_state["difficulties"].loc[opp, "Home"]
                    else:
                        v = DEFAULT_VALUES.get(opp, {}).get("Home", np.nan)
                        if pd.isna(v):
                            missing_opponents.add(opp)
                    vals.append(float(v) if not pd.isna(v) else np.nan)
                elif row["Away"] == team:
                    opp = row["Home"]
                    parts.append(str(opp).lower())
                    if opp in st.session_state["difficulties"].index:
                        v = st.session_state["difficulties"].loc[opp, "Away"]
                    else:
                        v = DEFAULT_VALUES.get(opp, {}).get("Away", np.nan)
                        if pd.isna(v):
                            missing_opponents.add(opp)
                    vals.append(float(v) if not pd.isna(v) else np.nan)
            except Exception:
                continue
        if parts:
            grid_text.loc[team, f"GW{gw}"] = ", ".join(parts)
            numeric_vals = [v for v in vals if not pd.isna(v)]
            grid_vals.loc[team, f"GW{gw}"] = np.nanmean(numeric_vals) if numeric_vals else np.nan
        else:
            grid_text.loc[team, f"GW{gw}"] = ""
            grid_vals.loc[team, f"GW{gw}"] = np.nan

# ---------------------
# UI: left sorted table, right fixture grid
# ---------------------
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader(f"Sorted Teams (GW{gw_start} → GW{gw_end}" + (f", excluding GW{excluded_gw})" if excluded_gw is not None else ")"))
    display = stats_df[["Team", "Name", "Total", "Avg", "Matches"]].copy()
    display["Avg"] = display["Avg"].round(1)

    num_rows = max(1, display.shape[0])
    row_height = 36
    header_pad = 40
    desired = num_rows * row_height + header_pad
    height_display = int(max(300, min(1400, desired)))

    st.dataframe(display, height=height_display, use_container_width=True, hide_index=True)

    if st.button("Download sorted CSV"):
        csv_bytes = display.to_csv(index=False).encode("utf-8")
        st.download_button("Download sorted_ticker.csv", data=csv_bytes, file_name="sorted_ticker.csv")
        st.success("Prepared CSV for download.")

with col_right:
    st.subheader(f"Fixture Grid (GW{gw_start} → GW{gw_end}) — excluded GW is greyed")
    cmap = cm.get_cmap("RdYlGn_r")
    try:
        vmin = np.nanmin(grid_vals.values)
        vmax = np.nanmax(grid_vals.values)
        if np.isnan(vmin) or np.isnan(vmax) or vmin == vmax:
            vmin, vmax = 500, 2000
    except Exception:
        vmin, vmax = 500, 2000
    norm = colors.Normalize(vmin=vmin, vmax=vmax)

    def style_cell_value(val):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return ""
        col = colors.to_hex(cmap(norm(val)))
        return f"background-color:{col};color:black;"

    styles = pd.DataFrame("", index=grid_text.index, columns=grid_text.columns)
    for r in grid_text.index:
        for c in grid_text.columns:
            gw_num = int(c.replace("GW", ""))
            v = grid_vals.loc[r, c]
            if excluded_gw is not None and gw_num == excluded_gw:
                styles.loc[r, c] = "background-color:#e6e6e6;color:#888888;"
            else:
                if not (pd.isna(v)):
                    styles.loc[r, c] = style_cell_value(v)

    styled = grid_text.style.apply(lambda row: styles.loc[row.name], axis=1)
    st.dataframe(styled, height=800, use_container_width=True)

# Footer / notes
st.markdown("""
---
### Notes about excluded GW
- The selected GW to exclude is **not** included in the Total / Avg calculations.
- The excluded GW **remains visible** in the Fixture Grid but is greyed out to show it was excluded.
- Only **one** GW can be excluded at a time for now.
""")

# --- START: AdSense/Legal Compliance Section (Placed BELOW Notes) ---

# Legal Text Definitions
privacy_text = """
### Privacy Policy 🛡️
This policy describes how we handle the data you provide.
1. **Data Collection:** We only collect anonymous usage statistics for site improvement.
2. **AdSense Integration:** We use Google AdSense for monetization, which collects data to serve personalized ads.
3. **Third Parties:** We do not sell or share your personal data with other third parties.
"""

terms_text = """
### Terms and Conditions 📜
By using this application, you agree to the following terms:
1. **Disclaimer:** This tool is provided "as is" for informational and entertainment purposes without warranty of any kind.
2. **Liability:** We are not liable for any damages or losses resulting from the use or inability to use this application.
3. **Changes:** We reserve the right to change these terms at any time.
"""

# Footer Links (Styled with custom HTML)
# Note: The 'margin-top' helps separate these links visually from the notes above.
st.markdown("""
    <style>
        .footer-links {
            display: flex;
            justify-content: center;
            gap: 20px;
            padding: 10px 0;
            font-size: 0.85rem;
            margin-top: 10px; 
        }
        .footer-links a {
            color: #888888; /* Subtle gray link color */
            text-decoration: none;
        }
        .footer-links a:hover {
            text-decoration: underline;
        }
    </style>
    <div class="footer-links">
        <a href="#privacy-policy">Privacy Policy</a>
        <a href="#terms-and-conditions">Terms & Conditions</a>
    </div>
    """, unsafe_allow_html=True)

# Content Reveal Section (Anchor targets and Expanders)
# The anchor links will scroll the user down to this final section of the page.

# Privacy Policy Section
st.markdown("<a id='privacy-policy'></a>", unsafe_allow_html=True)
with st.expander("Privacy Policy Details", expanded=False):
    st.markdown(privacy_text)

# Terms and Conditions Section
st.markdown("<a id='terms-and-conditions'></a>", unsafe_allow_html=True)
with st.expander("Terms and Conditions Details", expanded=False):
    st.markdown(terms_text)
    
# --- END: AdSense/Legal Compliance Section ---
