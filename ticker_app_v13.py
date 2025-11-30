# ============================================================
# ticker_app_v14.py — FIXED (NO js_eval)
# Browser LocalStorage via st.components HTML bridge
# ============================================================

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import requests
import json
from matplotlib import cm, colors
from typing import Tuple, Dict, List

st.set_page_config(layout="wide", page_title="FPL Season Ticker v14")

# -------------------------------------------------------------
# Browser LocalStorage bridge (NO js_eval)
# -------------------------------------------------------------

LOCAL_JS_WRAPPER = """
<script>
const pyKey = "%s";
const pyDefault = `%s`;

// Load existing
var existing = localStorage.getItem(pyKey);
if (!existing) {
    existing = pyDefault;
    localStorage.setItem(pyKey, pyDefault);
}

// Send the value to Streamlit
var streamlitDoc = window.parent.document;
var input = streamlitDoc.querySelector('[data-testid="stLocalStore-%s"]');
input.value = existing;
input.dispatchEvent(new Event("input", { bubbles: true }));

</script>
"""

def load_from_browser(key: str, default_obj):
    """
    Loads item from browser localStorage through an HTML component.
    Injects JS, writes value into a hidden Streamlit text_input.
    """
    default_json = json.dumps(default_obj)
    hidden_id = f"stLocalStore-{key}"

    # Create a hidden input to receive data
    placeholder = st.empty()
    hidden_box = placeholder.text_input("", key=hidden_id, label_visibility="collapsed")

    # Inject JS reading from localStorage and pushing into hidden input
    components.html(LOCAL_JS_WRAPPER % (key, default_json, key), height=0)

    if hidden_box:
        try:
            return json.loads(hidden_box)
        except:
            return default_obj
    return default_obj


def save_to_browser(key: str, value):
    """
    Saves an item to browser storage by injecting HTML+JS.
    """
    try:
        ser = json.dumps(value)
    except:
        ser = "{}"

    js = f"""
    <script>
        localStorage.setItem("{key}", `{ser}`);
    </script>
    """
    components.html(js, height=0)


# -------------------------------------------------------------
# FPL API endpoints
# -------------------------------------------------------------
FIX_API = "https://fantasy.premierleague.com/api/fixtures/"
BOOT_API = "https://fantasy.premierleague.com/api/bootstrap-static/"

# -------------------------------------------------------------
# Load FPL data
# -------------------------------------------------------------
@st.cache_data(ttl=3600)
def load_fpl_data() -> Tuple[pd.DataFrame, List[str], Dict[int, Dict[str, str]]]:
    try:
        fx = requests.get(FIX_API, timeout=10).json()
    except:
        fx = []

    try:
        boot = requests.get(BOOT_API, timeout=10).json()
    except:
        boot = {}

    # Parse teams
    teams = {}
    if "teams" in boot:
        for t in boot["teams"]:
            tid = t["id"]
            short = t["short_name"] or t["name"][:3]
            teams[tid] = {"name": t["name"], "short": short.upper()}

    # Fallback from fixtures
    for f in fx:
        for side in ["team_h", "team_a"]:
            tid = f.get(side)
            if tid and tid not in teams:
                teams[tid] = {"name": f"Team {tid}", "short": str(tid)[:3].upper()}

    # Build fixtures dataframe
    rows = []
    for f in fx:
        if f.get("event") is None:
            continue
        h = f["team_h"]; a = f["team_a"]
        rows.append({
            "GW": f["event"],
            "Home": teams[h]["short"],
            "Away": teams[a]["short"],
            "HomeName": teams[h]["name"],
            "AwayName": teams[a]["name"],
            "Kickoff": f.get("kickoff_time")
        })

    df = pd.DataFrame(rows).sort_values(["GW", "Kickoff"], na_position="last")
    team_list = sorted({t["short"] for t in teams.values()})

    return df, team_list, teams


# -------------------------------------------------------------
# Load data
# -------------------------------------------------------------
with st.spinner("Loading FPL data…"):
    df, team_codes, teams_full = load_fpl_data()

if df.empty:
    st.error("Could not load FPL data.")
    st.stop()

DEFAULT_VALUES = {t: {"Home": 1250, "Away": 1350} for t in team_codes}

# -------------------------------------------------------------
# Load user settings (browser)
# -------------------------------------------------------------
if "difficulties" not in st.session_state:
    browser_default = {t: DEFAULT_VALUES[t] for t in team_codes}
    loaded = load_from_browser("user_difficulties", browser_default)

    try:
        df_loaded = pd.DataFrame(loaded).T
        df_loaded.index.name = "Team"
        df_loaded = df_loaded[["Home", "Away"]].astype(float)
        st.session_state["difficulties"] = df_loaded
    except:
        st.session_state["difficulties"] = pd.DataFrame({
            "Team": team_codes,
            "Home": [DEFAULT_VALUES[t]["Home"] for t in team_codes],
            "Away": [DEFAULT_VALUES[t]["Away"] for t in team_codes],
        }).set_index("Team")


def ensure_all_teams():
    dfc = st.session_state["difficulties"]
    changed = False
    for t in team_codes:
        if t not in dfc.index:
            dfc.loc[t] = DEFAULT_VALUES[t]
            changed = True
    if changed:
        st.session_state["difficulties"] = dfc.reindex(team_codes)

ensure_all_teams()


# -------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------
with st.sidebar:
    min_gw = int(df["GW"].min())
    max_gw = int(df["GW"].max())

    gw_start, gw_end = st.slider("GW Range", min_gw, max_gw,
                                 (min(min_gw+11, max_gw), min(min_gw+15, max_gw)))

    opts = ["None"] + [str(g) for g in range(gw_start, gw_end+1)]
    excl = st.selectbox("Exclude GW", opts)
    excluded_gw = None if excl == "None" else int(excl)

    st.markdown("---")
    st.header("Difficulty Controls")

    edited = st.data_editor(st.session_state["difficulties"], use_container_width=True)
    if not edited.equals(st.session_state["difficulties"]):
        st.session_state["difficulties"] = edited
        save_to_browser("user_difficulties", edited.to_dict())
        st.success("Saved to your browser!")

    st.markdown("---")
    if st.button("Download CSV"):
        st.download_button(
            "Download now",
            st.session_state["difficulties"].to_csv().encode(),
            "difficulties.csv"
        )

    uploaded = st.file_uploader("Import CSV")
    if uploaded:
        try:
            imp = pd.read_csv(uploaded).set_index("Team")
            imp["Home"] = pd.to_numeric(imp["Home"], errors="coerce")
            imp["Away"] = pd.to_numeric(imp["Away"], errors="coerce")
            st.session_state["difficulties"] = imp
            save_to_browser("user_difficulties", imp.to_dict())
            st.success("Imported!")
        except Exception as e:
            st.error(str(e))

# -------------------------------------------------------------
# Compute stats
# -------------------------------------------------------------
if excluded_gw is None:
    sub = df[(df["GW"] >= gw_start) & (df["GW"] <= gw_end)]
else:
    sub = df[(df["GW"] >= gw_start) & (df["GW"] <= gw_end) & (df["GW"] != excluded_gw)]

short_to_full = {v["short"]: v["name"] for v in teams_full.values()}

team_stats = []

for team in team_codes:
    total = 0.0; matches = 0; cells = []
    for _, r in sub.iterrows():
        if r["Home"] == team:
            opp = r["Away"]
            val = st.session_state["difficulties"].loc[opp, "Home"]
            total += val; matches += 1
        elif r["Away"] == team:
            opp = r["Home"]
            val = st.session_state["difficulties"].loc[opp, "Away"]
            total += val; matches += 1
    avg = total / matches if matches else 0

    team_stats.append({
        "Team": team,
        "Name": short_to_full.get(team, team),
        "Total": total,
        "Avg": avg,
        "Matches": matches
    })

stats_df = pd.DataFrame(team_stats).sort_values("Total")

# -------------------------------------------------------------
# Fixture grid
# -------------------------------------------------------------
gw_list = list(range(gw_start, gw_end+1))
full_range = df[(df["GW"] >= gw_start) & (df["GW"] <= gw_end)]

grid_text = pd.DataFrame("", index=stats_df["Team"], columns=[f"GW{g}" for g in gw_list])
grid_vals = pd.DataFrame(np.nan, index=stats_df["Team"], columns=[f"GW{g}" for g in gw_list])

for t in stats_df["Team"]:
    for gw in gw_list:
        m = full_range[full_range["GW"] == gw]
        parts = []; vals = []
        for _, row in m.iterrows():
            if row["Home"] == t:
                opp = row["Away"]
                parts.append(opp.upper())
                vals.append(st.session_state["difficulties"].loc[opp, "Home"])
            elif row["Away"] == t:
                opp = row["Home"]
                parts.append(opp.lower())
                vals.append(st.session_state["difficulties"].loc[opp, "Away"])

        if parts:
            grid_text.loc[t, f"GW{gw}"] = ", ".join(parts)
            if vals:
                grid_vals.loc[t, f"GW{gw}"] = float(np.mean(vals))


# -------------------------------------------------------------
# Layout
# -------------------------------------------------------------
c1, c2 = st.columns([1,2])

with c1:
    st.subheader(f"Sorted Teams GW{gw_start}–GW{gw_end}" +
                 (f" (excl GW{excluded_gw})" if excluded_gw else ""))

    d = stats_df.copy()
    d["Avg"] = d["Avg"].round(1)

    rows = max(1, d.shape[0])
    st.dataframe(d, height=min(1400, 36 * rows + 50), hide_index=True)

with c2:
    st.subheader("Fixture Grid")

    cmap = cm.get_cmap("RdYlGn_r")
    try:
        vmin = np.nanmin(grid_vals.values)
        vmax = np.nanmax(grid_vals.values)
        if np.isnan(vmin) or vmin == vmax:
            vmin, vmax = 500, 2000
    except:
        vmin, vmax = 500, 2000
    norm = colors.Normalize(vmin, vmax)

    def style(v):
        if pd.isna(v):
            return ""
        return f"background-color:{colors.to_hex(cmap(norm(v)))};color:black;"

    styles = pd.DataFrame("", index=grid_text.index, columns=grid_text.columns)
    for r in grid_text.index:
        for c in grid_text.columns:
            gw_num = int(c.replace("GW", ""))
            if excluded_gw == gw_num:
                styles.loc[r, c] = "background-color:#e6e6e6;color:#888;"
            else:
                styles.loc[r, c] = style(grid_vals.loc[r, c])

    st.dataframe(grid_text.style.apply(lambda x: styles.loc[x.name], axis=1),
                 height=800)

st.markdown("""
---
### Notes
- Your difficulty settings are saved **privately in your browser**.
- They persist until you clear your browser data.
""")

