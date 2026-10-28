from pathlib import Path
import importlib
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_access

# Streamlit reruns the app in a long-lived process; refresh local helpers when
# their source changes so a previously imported version cannot hide new functions.
importlib.reload(data_access)
from data_access import DATA, ROOT, catalog, daily_grid, read_cases, values
from translations import NL, ABOUT_NL
from measurement_table import measurement_table

st.set_page_config(page_title="Second Opinion", page_icon="💧", layout="wide")

# Dutch for strings added in this redesign (everything else comes from translations.py).
NL_EXTRA = {
    "Text size": "Tekstgrootte", "Normal": "Normaal", "Large": "Groot", "Extra large": "Extra groot",
    "Cases to check": "Te controleren gevallen", "Look at measurements": "Metingen bekijken",
    "Settings for this list": "Instellingen voor deze lijst",
    "What to check first": "Wat eerst te controleren",
    "Choose what to look at": "Kies wat u wilt bekijken",
    "Start with the installation, then narrow down if needed.": "Begin met de installatie en verfijn daarna indien nodig.",
    "Nothing to show yet": "Nog niets te tonen",
    "Water operations dashboard": "Dashboard waterbeheer",
    "Historical measurements and investigation support": "Historische metingen en ondersteuning bij onderzoek",
    "AI assistant · notifications": "AI-assistent · meldingen",
    "Not connected yet": "Nog niet aangesloten",
    "Abnormality summaries and notifications will appear here after the model and assistant are connected. No analysis is running yet.": "Samenvattingen en meldingen over afwijkingen verschijnen hier zodra het model en de assistent zijn aangesloten. Er wordt nog geen analyse uitgevoerd.",
    "Local prototype · Historical daily data · No automatic validation": "Lokaal prototype · Historische daggegevens · Geen automatische validatie",
    "Filters and settings": "Filters en instellingen",
    "Local prototype": "Lokaal prototype",
}

# ---------- Sidebar: display settings only ----------
with st.sidebar:
    st.markdown('<div class="sidebar-brand"><span>◈</span><div><strong>Second Opinion</strong><small>Z-info prototype</small></div></div>', unsafe_allow_html=True)
    language = st.selectbox("Language / Taal", ["English", "Nederlands"], key="language")

def t(message):
    if language == "Nederlands":
        return NL_EXTRA.get(message) or NL.get(message, message)
    return message

with st.sidebar:
    with st.expander("Display / Weergave"):
        size_name = st.select_slider(t("Text size"), [t("Normal"), t("Large"), t("Extra large")], value=t("Normal"), key="size")
        mode = st.radio("Appearance / Weergave", ["Light / Licht", "Dark / Donker"], horizontal=True, key="appearance")

base_px = {t("Normal"): 14, t("Large"): 17, t("Extra large"): 20}[size_name]
dark = mode == "Dark / Donker"
bg, panel, fg, muted, border, accent, on_accent = (
    ("#17222e", "#243747", "#f4fafa", "#cfe0e2", "#617b8e", "#35bcd3", "#06242a") if dark
    else ("#f3f3f3", "#ffffff", "#243e56", "#465d6e", "#c8cdd2", "#24b5d2", "#ffffff")
)

st.markdown(f"""<style>
html {{font-size: {base_px}px;}}
html, body, button, input, textarea {{font-family: "Segoe UI", Calibri, sans-serif;}}
.stApp, [data-testid="stMain"], [data-testid="stHeader"] {{background: {bg}; color: {fg};}}
[data-testid="stSidebar"] {{background: {panel}; border-right: 1px solid {border};}}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{padding: .5rem .45rem;}}
.sidebar-brand {{display:flex; align-items:center; gap:10px; padding:12px; margin-bottom: 12px; background:{'#263e51' if dark else '#eef6fb'}; border:1px solid {border}; border-radius:10px;}}
.sidebar-brand > span {{color:#159fbc; font-size:27px; line-height:1;}}
.sidebar-brand strong {{display:block; color:{fg}; font-size:1.05rem;}}
.sidebar-brand small {{display:block; color:{muted}; font-size:.85rem;}}
.block-container {{max-width: none; padding: 4.5rem .75rem 5rem;}}
#MainMenu, footer {{visibility: hidden;}}
p, label, li, [data-testid="stMarkdownContainer"] {{font-size: 1rem; line-height: 1.6; color: {fg};}}
h1 {{font-size: 1.5rem !important; font-weight: 700 !important;}}
h2 {{font-size: 1.25rem !important; margin-top: .4rem !important;}}
h3 {{font-size: 1.1rem !important;}}
h1, h2, h3, [data-testid="stWidgetLabel"] p {{color: {fg} !important;}}
[data-testid="stWidgetLabel"] p {{font-weight: 700; font-size: 1rem;}}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{color: {muted} !important; font-size: 0.95rem;}}
*:focus-visible {{outline: 3px solid {accent} !important; outline-offset: 2px;}}

/* Cards and numbers */
div[data-testid="stMetric"] {{background: {panel}; border: 2px solid {border}; border-radius: 14px; padding: 1rem 1.2rem;}}
[data-testid="stMetricValue"] {{font-size: 2.4rem !important; font-weight: 700; color: {fg} !important;}}
[data-testid="stMetricLabel"] p {{color: {muted} !important; font-size: 1rem !important; font-weight: 700;}}
[data-testid="stVerticalBlockBorderWrapper"] {{background: {panel}; border: 2px solid {border} !important; border-radius: 14px;}}
[data-testid="stAlert"] {{border-radius: 12px; border: 2px solid {border}; background: {panel}; color: {fg};}}
[data-testid="stExpander"] {{background: {panel}; border: 2px solid {border}; border-radius: 12px;}}
[data-testid="stExpander"] summary p {{font-weight: 700; font-size: 1.05rem;}}

/* Inputs: tall, clear, high contrast */
[data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="base-input"], [data-baseweb="select"] [data-baseweb="select"] {{
  background-color: {panel} !important; color: {fg} !important; border-color: {border}; min-height: 2.2rem; border-radius: 3px;}}
[data-baseweb="select"] input, [data-baseweb="input"] input, [data-baseweb="base-input"] input {{color: {fg} !important; font-size: 1rem !important;}}
[data-baseweb="select"] span, [data-baseweb="select"] div {{color: {fg} !important; background-color: {panel} !important;}}
[data-testid="stSelectbox"] [data-baseweb="select"] > div, [data-testid="stTextInput"] [data-baseweb="input"] > div,
[data-testid="stDateInput"] [data-baseweb="input"] > div, [data-testid="stTextInput"] input, [data-testid="stDateInput"] input {{
  background: {panel} !important; color: {fg} !important; border-color: {border} !important;}}
[data-testid="stSelectbox"] [role="group"], [data-testid="stSelectbox"] input,
[data-testid="stSelectbox"] [role="group"] button, [data-testid="stDateInputField"],
[data-testid="stDateInputField"] [role="group"], [data-testid="stDateInputField"] span {{
  background-color: {panel} !important; color: {fg} !important; border-color: {border} !important;}}
[data-testid="stSelectbox"] [role="group"] button svg {{color: {fg} !important; fill: {fg} !important;}}
[data-baseweb="select"] svg, [data-baseweb="input"] svg {{fill: {fg} !important; color: {fg} !important;}}
[data-baseweb="input"] input, [data-baseweb="base-input"] input {{background-color: {panel} !important;}}
[data-baseweb="popover"] [role="listbox"], [data-baseweb="popover"] [role="option"] {{background-color: {panel} !important; color: {fg} !important;}}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{color:{accent} !important;}}

/* Radio groups look like big buttons (used for the main navigation) */
[data-testid="stRadio"] [role="radiogroup"] {{gap: 0.6rem; flex-wrap: wrap;}}
[data-testid="stRadio"] [role="radiogroup"] label {{background: {panel}; border: 1px solid {border}; border-radius: 4px;
  padding: 0.25rem 0.65rem; cursor: pointer; min-height: 2.1rem; align-items: center;}}
[data-testid="stRadio"] [role="radiogroup"] label > div:first-child {{display: none;}}
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {{background: {accent}; border-color: {accent};}}
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) p {{color: {on_accent} !important; font-weight: 700;}}
[data-testid="stRadio"] [role="radiogroup"] label p {{font-size: 1.1rem; margin: 0;}}
.product-bar {{background: #17548b; padding: 12px 20px; border-radius: 5px; margin-bottom: .35rem; display:flex; align-items:center; gap:14px;}}
.product-bar .brand-name {{font-size: 1.65rem; font-weight:750; letter-spacing:-.04em; color:#fff !important;}}
.product-bar .brand-name b {{color:#42c4df !important;}}
.product-bar .brand-divider {{height:28px; width:1px; background:#ffffff70;}}
.product-bar .product-name {{font-size:1rem; font-weight:600; color:#e5f5ff !important;}}
.app-footer {{border-top: 1px solid {border}; color: {muted}; padding: 14px 2px; font-size: .9rem; margin-top: 16px;}}
.assistant-float {{position: fixed; z-index: 100; bottom: 20px; right: 24px; font-family: "Segoe UI", sans-serif; color: {fg};}}
.assistant-float summary {{list-style: none; cursor: pointer; display: flex; align-items: center; gap: 10px; background: #17548b; color: #fff; border-radius: 28px; padding: 7px 14px 7px 7px; box-shadow: 0 4px 14px #0004; font-weight: 700;}}
.assistant-float summary::-webkit-details-marker {{display:none;}}
.assistant-face {{display:flex; align-items:center; justify-content:center; width:38px; height:38px; border:2px solid #9be6f2; border-radius:50%; background:#65c8e3; font-size:23px; line-height:1;}}
.assistant-card {{position:absolute; bottom:62px; right:0; width:300px; max-width:80vw; background:{panel}; color:{fg}; border:1px solid {border}; border-radius:12px; padding:15px; box-shadow:0 4px 18px #0003; line-height:1.45;}}
.assistant-card strong {{display:block; color:{fg}; margin-bottom:6px;}}
</style>""", unsafe_allow_html=True)

CHART = dict(template="plotly_dark" if dark else "plotly_white", paper_bgcolor=panel, plot_bgcolor=panel,
             font=dict(color=fg, size=base_px - 3))

@st.cache_data(show_spinner=t("Loading measurement catalog..."))
def load_catalog():
    return catalog()

@st.cache_data(show_spinner=t("Loading daily records..."))
def load_values(path):
    return values(Path(path))

def text(value, default=None):
    default = t("Not provided") if default is None else default
    return str(value).strip() if pd.notna(value) and str(value).strip() else default

def point_label(row):
    return " | ".join(text(row.get(k), "—") for k in ["MeasurementPointID", "MeasurementObjectDescription", "ParameterDescription", "Unit"])

# ---------- Header and navigation ----------
st.markdown(f'<div class="product-bar"><span class="brand-name"><b>Z</b>-info</span><span class="brand-divider"></span><span class="product-name">Second Opinion · {t("Local prototype")}</span></div>', unsafe_allow_html=True)
st.caption(t("Historical measurements and investigation support"))
PAGES = {"daily": t("Daily measurements"), "queue": t("Cases to check"), "explore": t("Look at measurements"), "assistant": t("Analysis assistant"), "about": t("About & handover")}
page = st.radio(t("Navigate"), list(PAGES), format_func=PAGES.get, horizontal=True, label_visibility="collapsed", key="page")
st.markdown(f'''<details class="assistant-float"><summary aria-label="{t('AI assistant · notifications')}"><span class="assistant-face" aria-hidden="true">🤖</span>{t('AI assistant · notifications')}</summary><div class="assistant-card"><strong>{t('Not connected yet')}</strong>{t('Abnormality summaries and notifications will appear here after the model and assistant are connected. No analysis is running yet.')}</div></details>''', unsafe_allow_html=True)

# ---------- Page 1: cases to check ----------
if page == "queue":
    st.header(t("Investigation queue"))
    st.write(t("Review the cases supplied by the analysis team in their recorded order. Cases outside the budget remain visible."))

    default_path = str(ROOT / "data" / "case_results.csv")
    path_text = st.session_state.get("case_path", default_path)
    path = Path(path_text).expanduser()
    with st.expander(t("Settings for this list"), expanded=not path.is_file()):
        case_path = st.text_input(t("Local case results CSV"), value=default_path, key="case_path", help=t("Use the agreed results format described in About & handover."))
    path = Path(case_path).expanduser()

    if not path.is_file():
        st.subheader(t("Model results are not connected yet"))
        st.warning(t("The queue accepts local results from the analysis team. Until those are supplied, no anomalies are claimed or shown."))
        st.caption(t("The absence of results does not mean there are no unusual readings. Use Explore measurements to inspect the source data."))
        st.stop()
    try:
        cases = read_cases(path)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.error(f"{t('Could not read case results')}: {exc}")
        st.stop()
    if cases.empty:
        st.info(t("The results file contains no cases. Check its coverage and generation method before interpreting this as a clean period."))
        st.stop()

    with st.container(border=True):
        c1, c2 = st.columns(2)
        budget = c1.number_input(t("Cases available to review"), min_value=0, max_value=len(cases), value=min(10, len(cases)), step=1)
        minutes = c2.number_input(t("Minutes per case (assumption)"), min_value=0, value=5, step=1, help=t("Replace this illustrative assumption with an operator-provided estimate."))
    selected, deferred = cases.iloc[:budget], cases.iloc[budget:]

    a, b, c = st.columns(3)
    a.metric(t("Cases in results"), len(cases))
    b.metric(t("For review"), len(selected))
    c.metric(t("Deferred"), len(deferred))
    st.caption(f"{t('Estimated review time')}: {budget * minutes} {t('minutes')}, {t('using the adjustable assumption of')} {minutes} {t('minutes per case. Deferred cases may still need attention.')}")

    for title, frame in [(t("For review"), selected), (t("Deferred"), deferred)]:
        st.subheader(f"{title} · {len(frame)}")
        if frame.empty:
            st.caption(t("No cases in this group."))
        else:
            display = frame[["rank", "installation", "measurement_point_id", "date", "reason"]].rename(columns={
                "rank": t("Rank"), "installation": t("Installation"), "measurement_point_id": t("Point"), "date": t("Date"), "reason": t("Reason")})
            st.dataframe(display, hide_index=True, width="stretch")

    st.header(t("Case evidence"))
    case_id = st.selectbox(t("Select a case"), cases["case_id"].tolist(), format_func=lambda v: f"{v} · {cases.loc[cases['case_id'] == v, 'installation'].iloc[0]}")
    case = cases.loc[cases["case_id"] == case_id].iloc[0]

    with st.container(border=True):
        st.subheader(t("Why it was flagged"))
        st.write(case["reason"])
        st.write(f"**{t('Installation')}:** {case['installation']}  \n**{t('Point')}:** {case['measurement_point_id']}  \n**{t('Date')}:** {case['date']}")
    with st.container(border=True):
        st.subheader(t("What to check first"))
        st.write(text(case.get("suggested_check"), t("Not supplied")))
        for column, label in [("value", "Recorded value"), ("unit", "Unit"), ("peer_context", "Peer context")]:
            st.write(f"**{t(label)}:** {text(case.get(column), t('Not supplied'))}")

    st.subheader(t("Measurement history"))
    case_file = (DATA / "MeasurementValues" / f"{case['installation']}.csv.gz").resolve()
    values_root = (DATA / "MeasurementValues").resolve()
    if case_file.parent != values_root or not case_file.is_file():
        st.info(t("History is unavailable for this installation in the local export."))
    else:
        history = load_values(str(case_file))
        history = history.loc[(history["MeasurementPointID"] == case["measurement_point_id"]) & history["ParsedDate"].notna() & history["NumericValue"].notna()].copy()
        case_date = pd.Timestamp(case["date"])
        history = history.loc[history["ParsedDate"].between(case_date - pd.Timedelta(days=90), case_date)].sort_values("ParsedDate")
        if history.empty:
            st.info(t("No numeric records were found for this point in the 90 days up to the case date."))
        else:
            hu = history["Unit"].dropna().unique()
            fig = px.scatter(history, x="ParsedDate", y="NumericValue", color="Unit" if len(hu) > 1 else None, facet_row="Unit" if len(hu) > 1 else None,
                             hover_data=["Value", "Unit", "ProcessCode"], labels={"ParsedDate": t("Date"), "NumericValue": t("Recorded value"), "Unit": t("Unit")})
            if len(hu) > 1:
                fig.update_yaxes(matches=None)
            fig.update_traces(marker=dict(size=10))
            fig.add_vline(x=case_date.timestamp() * 1000, line_dash="dash", line_width=3, line_color="#d9741a")
            fig.update_layout(**CHART)
            st.plotly_chart(fig, width="stretch")
            st.caption(t("Source rows from the 90 days up to the case date. The dashed line marks the case date; repeated dates remain separate."))
    st.caption(t("Ranking and explanations come from the supplied results. Confirm the method and its coverage with the analysis team."))

# ---------- Daily source records ----------
elif page == "daily":
    st.header(t("Daily measurement table"))
    if not DATA.is_dir():
        st.error(t("Local TAI export not found. Expected data/tai/extracted/."))
        st.stop()
    points, names = load_catalog()
    available = {p.name[:-7] for p in (DATA / "MeasurementValues").glob("*.csv.gz")}
    if points.empty or "InstallationCode" not in points:
        st.error(t("No measurement-point catalog found."))
        st.stop()
    installations = sorted(set(points["InstallationCode"].dropna().astype(str)) & available)
    if not installations:
        st.error(t("No installation has both metadata and daily values."))
        st.stop()
    with st.sidebar:
        st.subheader(t("Filter"))
        installation = st.selectbox(t("Installation"), installations, format_func=lambda x: f"{names.get(x) or t('Description unavailable')} ({x})", key="daily_installation")
    daily = load_values(str(DATA / "MeasurementValues" / f"{installation}.csv.gz"))
    dated = daily["ParsedDate"].dropna()
    if dated.empty:
        st.warning(t("No dated records are available for this installation."))
        st.stop()
    with st.sidebar:
        process_options = sorted(daily["ProcessCode"].dropna().astype(str).unique().tolist())
        all_label = t("All processes")
        process = st.selectbox(t("Process code"), [all_label] + process_options, key="daily_process")
        query = st.text_input(t("Filter points"), placeholder=t("Search name or point ID"), key="daily_query").strip().casefold()
    c1, c2 = st.columns([2, 3])
    end = c1.date_input(t("End date"), value=dated.max().date(), min_value=dated.min().date(), max_value=dated.max().date(), key="grid_end")
    days = c2.slider(t("Number of days"), min_value=1, max_value=14, value=8, key="grid_days")
    start = max(dated.min().date(), end - pd.Timedelta(days=days - 1))
    subset = daily if process == all_label else daily.loc[daily["ProcessCode"] == process]
    metadata = points.loc[points["InstallationCode"] == installation]
    grid = daily_grid(subset, metadata, start, end)
    if query and not grid.empty:
        match = grid["MeasurementPointID"].str.casefold().str.contains(query, regex=False) | grid["MeasurementObjectDescription"].str.casefold().str.contains(query, regex=False)
        grid = grid.loc[match]
    if grid.empty:
        st.info(t("No source records match this selection."))
    else:
        st.caption(f"{names.get(installation) or installation} · {start} — {end} · {len(grid)} {t('Rows shown')}")
        st.markdown(measurement_table(grid, names.get(installation) or installation, dark=dark, dutch=language == "Nederlands", font_size=base_px), unsafe_allow_html=True)
    st.caption(t("Source rows are shown individually. Repeated dates are not combined, and no validation status is inferred."))

# ---------- Page 2: look at measurements ----------
elif page == "explore":
    st.header(t("Explore measurements"))
    st.write(t("Select an installation, process and measurement point to inspect recorded history. This view does not detect anomalies."))
    if not DATA.is_dir():
        st.error(t("Local TAI export not found. Expected data/tai/extracted/."))
        st.stop()
    points, names = load_catalog()
    available = {p.name[:-7] for p in (DATA / "MeasurementValues").glob("*.csv.gz")}
    if points.empty or "InstallationCode" not in points:
        st.error(t("No measurement-point catalog found."))
        st.stop()
    installations = sorted(set(points["InstallationCode"].dropna().astype(str)) & available)
    if not installations:
        st.error(t("No installation has both metadata and daily values."))
        st.stop()

    with st.container(border=True):
        st.subheader(t("Choose what to look at"))
        st.caption(t("Start with the installation, then narrow down if needed."))
        f1, f2 = st.columns(2)
        installation = f1.selectbox(t("Installation"), installations, format_func=lambda x: f"{names.get(x) or t('Description unavailable')} ({x})")
        all_values = load_values(str(DATA / "MeasurementValues" / f"{installation}.csv.gz"))
        subset = points.loc[points["InstallationCode"] == installation].copy()
        process_options = sorted(all_values["ProcessCode"].dropna().astype(str).unique().tolist())
        all_label = t("All processes")
        process = f2.selectbox(t("Process code"), [all_label] + process_options)
        if process != all_label:
            ids = set(all_values.loc[all_values["ProcessCode"] == process, "MeasurementPointID"].dropna().astype(str))
            subset = subset.loc[subset["MeasurementPointID"].astype(str).isin(ids)]
        f3, f4 = st.columns(2)
        query = f3.text_input(t("Find a measurement point"), placeholder=t("Name, ID, parameter or unit")).strip().casefold()
        subset["label"] = subset.apply(point_label, axis=1)
        if query:
            subset = subset.loc[subset["label"].str.casefold().str.contains(query, regex=False)]
        if subset.empty:
            st.warning(t("No points match the selected filters."))
            st.stop()
        subset = subset.drop_duplicates("MeasurementPointID").set_index("MeasurementPointID", drop=False)
        point = f4.selectbox(t("Measurement point"), subset.index.astype(str).tolist(), format_func=lambda x: subset.loc[x, "label"])
        meta = subset.loc[point]
        records = all_values.loc[all_values["MeasurementPointID"] == point].copy()
        if process != all_label:
            records = records.loc[records["ProcessCode"] == process]
        dates = records["ParsedDate"].dropna()
        if dates.empty:
            st.warning(t("No dated records are available for this selection."))
            st.stop()
        low, high = dates.min().date(), dates.max().date()
        date_range = st.date_input(t("Date range"), (low, high), min_value=low, max_value=high)

    if not isinstance(date_range, (tuple, list)) or len(date_range) != 2:
        st.info(t("Choose both a start and end date."))
        st.stop()
    records = records.loc[records["ParsedDate"].between(pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]))].sort_values("ParsedDate")
    numeric = records.dropna(subset=["NumericValue", "ParsedDate"])
    units = sorted(records["Unit"].dropna().astype(str).unique().tolist())

    st.header(text(meta.get("MeasurementObjectDescription")))
    st.caption(f"{text(meta.get('ParameterDescription'))} · {text(meta.get('ProductDescription'))} · {t('Catalog unit')}: {text(meta.get('Unit'))}")
    duplicates = int(records["ParsedDate"].duplicated(keep=False).sum())
    a, b, c, d = st.columns(4)
    a.metric(t("Source records"), len(records))
    b.metric(t("Dates with records"), records["ParsedDate"].nunique())
    c.metric(t("Blank values"), int(records["Value"].fillna("").str.strip().eq("").sum()))
    d.metric(t("Repeated-date rows"), duplicates)
    if duplicates:
        st.warning(t("Some dates have multiple source rows. They remain separate and are not averaged."))
    if len(units) > 1:
        st.warning(t("Multiple units are present. They are plotted separately; confirm compatibility before comparison."))
    if numeric.empty:
        st.info(t("No numeric records in this date range."))
    else:
        fig = px.scatter(numeric, x="ParsedDate", y="NumericValue", color="Unit" if len(units) > 1 else None, facet_row="Unit" if len(units) > 1 else None,
                         hover_data=["Value", "Unit", "ProcessCode", "SubProcessDescription"], labels={"ParsedDate": t("Date"), "NumericValue": t("Recorded value"), "Unit": t("Unit")})
        if len(units) > 1:
            fig.update_yaxes(matches=None)
        fig.update_traces(marker=dict(size=10))
        fig.update_layout(**CHART, height=450 if len(units) < 2 else max(450, len(units) * 260), margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, width="stretch")
    st.caption(t("Each marker is a source row. Dates are daily; no cause, operating limit or diagnosis is inferred."))
    with st.expander(t("Point metadata")):
        st.dataframe(meta.drop(labels=["label"], errors="ignore").rename("Value").to_frame(), width="stretch")
    with st.expander(t("Source records")):
        columns = [c for c in ["Date", "Value", "Unit", "ProcessCode", "SubProcessDescription", "ProductBalance"] if c in records]
        st.dataframe(records[columns], hide_index=True, width="stretch")

# ---------- Assistant integration ----------
elif page == "assistant":
    st.header(t("Analysis assistant"))
    st.subheader(t("Analysis assistant is not connected"))
    st.info(t("A future assistant can explain the selected case using verified model output and source records. No AI model or external service is connected to this prototype yet."))
    st.subheader(t("Questions the assistant should help answer"))
    for question in ["Why was this reading flagged?", "How does it compare with this point's history?", "What peer evidence is available?", "What should I check next?"]:
        st.markdown(f"- {t(question)}")
    st.caption(t("The assistant must distinguish observations from possible causes and keep the operator in control."))

# ---------- Page 3: about ----------
else:
    st.header(t("About & handover"))
    st.markdown(ABOUT_NL if language == "Nederlands" else """This local prototype brings a review queue and the recorded measurement history together. It does not calculate anomaly scores or validate data.

**Next integration:** the analysis team supplies a local CSV with `case_id`, `installation`, `measurement_point_id`, `date`, `reason`, and a unique positive numeric `rank` (lower is reviewed first). Optional fields: `value`, `unit`, `peer_context`, `suggested_check`. Dates should be ISO format. The CSV should contain only results the team is authorized to use locally.

The queue uses the supplied order, not a verified probability or severity. Review-time estimates are assumptions until confirmed by operators. The daily export is historical and has no confirmed anomaly labels. Peer context, existing limits, model evaluation and real-world impact remain unverified until supplied and checked by the team.

Source data and results remain on this computer. Never commit partner data or keys.
""")

st.markdown(f'<div class="app-footer">{t("Local prototype · Historical daily data · No automatic validation")}</div>', unsafe_allow_html=True)
