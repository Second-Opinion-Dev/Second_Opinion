"""Local three-year measurements and public, national KNMI rain context."""
from pathlib import Path
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_access import DATA, catalog, values
from src.history_detector.history_detector import MEASUREMENTS
from yearly_metrics import YEARS, annual_medians

st.set_page_config(page_title="Second Opinion | Rain and treatment", page_icon="💧", layout="wide")

TEXT = {
    "title": ("Regen en waterzuivering", "Rain and wastewater treatment"),
    "simple": ("In gewone woorden", "In simple words"),
    "explain": (
        "Een waterzuivering werkt een beetje als een grote schoonmaakploeg: kleine bacteriën helpen het water schoon te maken. Als er veel regen in het riool komt, moet de installatie mogelijk meer water verwerken. Minder regen kan die druk verminderen, maar dit verschilt per installatie. De grafieken tonen Nederlandse regen en lokale metingen in 2023–2025. Ze bewijzen niet dat regen een verandering veroorzaakte of dat de zuivering beter werkte. Een elektriciteitsmeter laat ook niet zien welk apparaat de stroom gebruikte.",
        "A treatment plant is like a big cleaning team: tiny bacteria help clean the water. When rain enters the sewer, the plant may have more water to handle. Less rain may reduce that pressure, but every plant is different. These graphs show rainfall across the Netherlands and local plant measurements in 2023–2025. They do not prove that rain caused a change or made treatment work better. An electricity meter also cannot tell us which machine used the power."),
    "plant": ("Kies een installatie", "Choose a plant"), "point": ("Kies een meetpunt", "Choose a measurement point"),
    "context": ("Kies een procescontext", "Choose a process context"),
    "missing": ("Lokale gegevens niet beschikbaar", "Local data unavailable"),
    "rain": ("1 · Hoeveel regen viel er?", "1 · How much rain fell?"),
    "rain_note": ("Landelijk jaargemiddelde van automatische KNMI-stations, in millimeter. Dit is geen lokale meting bij de geselecteerde installatie.", "National annual average from automatic KNMI stations, in millimetres. This is not rainfall measured at the selected plant."),
    "volume": ("2 · Hoeveel inkomend water werd gemeten?", "2 · How much incoming water was recorded?"),
    "oxygen": ("3 · Hoeveel zuurstof werd gemeten?", "3 · How much oxygen was recorded?"),
    "ammonium": ("4 · Hoeveel ammonium werd gemeten?", "4 · How much ammonium was recorded?"),
    "electricity": ("5 · Wat liet een elektriciteitsmeter zien?", "5 · What did an electricity meter record?"),
    "annual": ("Middelste beschikbare dagwaarde per jaar", "Median available daily reading per year"),
    "count": ("dagen met een bruikbare meting", "days with a usable reading"),
    "excluded": ("dagen met meerdere bronwaarden weggelaten", "days with multiple source records excluded"),
    "no_data": ("Geen geschikte metingen beschikbaar voor deze installatie.", "No suitable readings are available for this plant."),
    "elec_note": ("Dit is één geselecteerd kWh-meetpunt, niet automatisch het totale verbruik van de installatie. De waarde kan verbruik of productie zijn; controleer de betekenis en de aggregatie met TAI. De meter toont niet of verwarming, beluchting of iets anders stroom gebruikte.", "This is one selected kWh point, not necessarily the plant's total electricity use. It may record consumption or production; confirm its meaning and aggregation with TAI. The meter does not show whether heating, aeration or anything else used the power."),
    "limits": ("Regen is een landelijk gemiddelde; metingen zijn lokaal. Zonder lokaal weer, procesgegevens en bevestigde meetdefinities kunnen we geen oorzaak, biologisch voordeel of besparing vaststellen.", "Rainfall is a national average; plant readings are local. Without local weather, process data and confirmed measurement definitions, we cannot establish a cause, biological benefit or savings."),
    "sources": ("Bronnen", "Sources"),
    "size": ("Tekstgrootte", "Text size"), "normal": ("Normaal", "Normal"), "large": ("Groot", "Large"), "xl": ("Extra groot", "Extra large"),
    "appearance": ("Weergave", "Appearance"), "light": ("Licht", "Light"), "dark": ("Donker", "Dark"),
    "settings": ("Weergave-instellingen", "Display settings"),
}


def remembered(widget, label, options, key, default, **kw):
    """Widget whose choice survives switching pages (Streamlit forgets widgets not drawn on a page)."""
    if "w_" + key not in st.session_state:
        saved = st.session_state.get("saved_" + key, default)
        st.session_state["w_" + key] = saved if saved in options else default
    def keep(): st.session_state["saved_" + key] = st.session_state["w_" + key]
    return widget(label, options, key="w_" + key, on_change=keep, **kw)


# ---------- Sidebar: plant on top (filled later), display settings below ----------
plant_box = st.sidebar.container()
with st.sidebar:
    st.divider()
    LANG = remembered(st.selectbox, "Language / Taal", ["English", "Nederlands"], "lang", "English")
    NL = LANG == "Nederlands"
    def tr(key): return TEXT[key][0 if NL else 1]
    size = remembered(st.select_slider, tr("size"), ["normal", "large", "xl"], "size", "large", format_func=tr)
    theme = remembered(st.radio, tr("appearance"), ["light", "dark"], "theme", "light", horizontal=True, format_func=tr)

base_px = {"normal": 18, "large": 20, "xl": 23}[size]
dark = theme == "dark"
bg, panel, fg, muted, border, accent, on_accent = (
    ("#0f1f23", "#1a3238", "#f4fafa", "#cfe0e2", "#5d7c82", "#6fd0de", "#06242a") if dark
    else ("#f3f7f7", "#ffffff", "#0f2a2e", "#37535a", "#9fbbbd", "#0a6677", "#ffffff"))
COLORS = ({"rain": "#7fb4e0", "influent_volume": "#6fd0de", "oxygen": "#7fd6a0", "ammonium": "#c9a4f0", "electricity": "#f0b070"} if dark
          else {"rain": "#2f6f9f", "influent_volume": "#0a6677", "oxygen": "#2a8050", "ammonium": "#7a4fa8", "electricity": "#c0651a"})

st.markdown(f"""<style>
html {{font-size: {base_px}px;}}
html, body, [class*="st-"], button, input {{font-family: Arial, Helvetica, sans-serif;}}
.stApp, [data-testid="stMain"], [data-testid="stHeader"] {{background: {bg}; color: {fg};}}
[data-testid="stSidebar"] {{background: {panel}; border-right: 2px solid {border};}}
.block-container {{max-width: 1100px; padding-top: 2.2rem; padding-bottom: 4rem;}}
#MainMenu, footer {{visibility: hidden;}}
p, label, li, [data-testid="stMarkdownContainer"] {{font-size: 1rem; line-height: 1.6; color: {fg};}}
h1 {{font-size: 2.3rem !important; font-weight: 700 !important; color: {fg} !important;}}
h2, h3 {{color: {fg} !important; font-size: 1.4rem !important;}}
[data-testid="stWidgetLabel"] p {{font-weight: 700; color: {fg} !important;}}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{color: {muted} !important; font-size: 0.95rem;}}
a {{color: {accent} !important; font-weight: 700;}}
*:focus-visible {{outline: 3px solid {accent} !important; outline-offset: 2px;}}
.brand {{background: {accent}; color: {on_accent}; padding: 0.8rem 1.2rem; border-radius: 12px; font-weight: 700; font-size: 1.3rem; margin-bottom: 1.4rem;}}
[data-testid="stVerticalBlockBorderWrapper"] {{background: {panel}; border: 2px solid {border} !important; border-radius: 14px;}}
[data-testid="stAlert"] {{border-radius: 12px; border: 2px solid {border}; background: {panel}; color: {fg};}}
[data-baseweb="select"] > div, [data-baseweb="input"] > div {{background-color: {panel}; color: {fg}; border: 2px solid {border}; min-height: 3rem; border-radius: 10px;}}
[data-baseweb="select"] input, [data-baseweb="select"] div {{color: {fg} !important;}}
[data-testid="stRadio"] [role="radiogroup"] label {{background: {panel}; border: 2px solid {border}; border-radius: 10px; padding: 0.4rem 1rem;}}
[data-testid="stRadio"] [role="radiogroup"] label > div:first-child {{display: none;}}
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {{background: {accent}; border-color: {accent};}}
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) p {{color: {on_accent} !important; font-weight: 700;}}
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=300, max_entries=2)
def load_catalog(): return catalog(DATA)


@st.cache_data(show_spinner=False, max_entries=8)
def load_plant(path, stamp): return values(Path(path))


def eligible_points(points, metric):
    mask = pd.Series(True, index=points.index)
    for column, expected in MEASUREMENTS[metric].items():
        if column not in points: return points.iloc[0:0]
        actual = points[column].fillna("").astype(str).str.strip()
        mask &= actual.eq(expected) if column == "Unit" else actual.str.casefold().eq(expected.casefold())
    return points.loc[mask]


def fmt_label(row):
    description = row.get("MeasurementObjectDescription", "")
    description = "" if pd.isna(description) else str(description)
    return f"{description or row['MeasurementPointID']} · {row['MeasurementPointID']} · {row.get('Unit', '')}"


def plot_years(summary, unit, color, *, show_count=True):
    hover = "%{x}<br>%{y:.2f} " + str(unit)
    if show_count: hover += "<br>n=%{customdata}"
    top = pd.to_numeric(summary["median"], errors="coerce").max()
    fig = go.Figure(go.Bar(x=[str(y) for y in YEARS], y=summary["median"], customdata=summary["count"], marker_color=color,
        text=[f"{v:,.1f}" if pd.notna(v) else "—" for v in summary["median"]], textposition="outside", cliponaxis=False,
        textfont=dict(size=base_px, color=fg), hovertemplate=hover + "<extra></extra>"))
    fig.update_layout(template="plotly_dark" if dark else "plotly_white", paper_bgcolor=panel, plot_bgcolor=panel,
        font=dict(color=fg, size=base_px - 3), height=300, margin=dict(l=10, r=10, t=30, b=10), bargap=0.45,
        yaxis=dict(title=str(unit), range=[0, top * 1.2] if pd.notna(top) and top > 0 else None), xaxis_title=None)
    st.plotly_chart(fig, width="stretch")


def show_measurement(points, records, metric):
    candidates = eligible_points(points, metric).drop_duplicates("MeasurementPointID")
    relevant = records.loc[records.ParsedDate.dt.year.isin(YEARS) & records.NumericValue.notna()]
    coverage = relevant.groupby("MeasurementPointID").ParsedDate.nunique()
    candidates = candidates.loc[candidates.MeasurementPointID.isin(coverage.index)]
    if candidates.empty:
        st.info(tr("no_data")); return
    indexed = candidates.set_index("MeasurementPointID", drop=False)
    options = indexed.index.astype(str).tolist()
    preferred = max(options, key=lambda item: int(coverage.get(item, 0)))
    point = st.selectbox(tr("point"), options, index=options.index(preferred), format_func=lambda x: fmt_label(indexed.loc[x]), key="point_" + metric)
    expected_unit = str(indexed.loc[point, "Unit"])
    selected = records.loc[records.MeasurementPointID.eq(point) & records.Unit.fillna("").eq(expected_unit)].copy()
    show_series(selected, expected_unit, metric)


def show_series(selected, unit, key):
    context_columns = [c for c in ("SubProcessCodeOrigin", "ProcessCode", "Product", "ProductBalance", "InstallationCodeDestination", "SubProcessDestination") if c in selected]
    selected[context_columns] = selected[context_columns].fillna("").astype(str)
    contexts = selected[context_columns].drop_duplicates()
    if len(contexts) > 1:
        choices = [tuple(row) for row in contexts.itertuples(index=False, name=None)]
        context = st.selectbox(tr("context"), choices, format_func=lambda row: " · ".join(x for x in row if x) or "—", key="context_" + key)
        for column, value in zip(context_columns, context): selected = selected.loc[selected[column].eq(value)]
    summary, excluded = annual_medians(selected)
    plot_years(summary, unit, COLORS.get(key, COLORS["electricity"]))
    counts = " · ".join(f"{year}: {int(summary.loc[year, 'count'])}" for year in YEARS)
    st.caption(f"{tr('annual')} ({unit})  \n{counts} {tr('count')} · {excluded} {tr('excluded')}")


# ---------- Header ----------
st.markdown('<div class="brand">💧 Second Opinion</div>', unsafe_allow_html=True)
st.title(tr("title"))
with st.container(border=True):
    st.subheader(tr("simple"))
    st.write(tr("explain"))

# ---------- Data ----------
try:
    points, names = load_catalog()
    files = {p.name[:-7]: p for p in (DATA / "MeasurementValues").glob("*.csv.gz")}
    groups = [set(eligible_points(points, m).InstallationCode.dropna()) for m in ("influent_volume", "oxygen", "ammonium")]
    plants = sorted(set.intersection(*groups) & set(files))
    if not plants: st.error(tr("missing")); st.stop()
    # Prefer a plant with actual observations in all three cohorts and a kWh
    # point. Metadata alone does not guarantee that a point has readings.
    preferred_plant = plants[0]
    for candidate in plants[:8]:
        candidate_path = files[candidate]
        candidate_records = load_plant(str(candidate_path), candidate_path.stat().st_mtime_ns)
        observed = candidate_records.loc[candidate_records.ParsedDate.dt.year.isin(YEARS) & candidate_records.NumericValue.notna()]
        ids = set(observed.MeasurementPointID.dropna())
        metadata = points.loc[points.InstallationCode.eq(candidate)]
        has_metrics = all(bool(ids & set(eligible_points(metadata, m).MeasurementPointID)) for m in ("influent_volume", "oxygen", "ammonium"))
        energy_ids = set(metadata.loc[metadata.Unit.fillna("").str.casefold().eq("kwh"), "MeasurementPointID"])
        if has_metrics and ids & energy_ids:
            preferred_plant = candidate
            break
    with plant_box:
        plant = st.selectbox(tr("plant"), plants, index=plants.index(preferred_plant), format_func=lambda x: f"{names.get(x) or x} ({x})")
    point_catalog = points.loc[points.InstallationCode.eq(plant)].copy()
    path = files[plant]
    readings = load_plant(str(path), path.stat().st_mtime_ns)
except (OSError, ValueError, KeyError, pd.errors.ParserError) as exc:
    st.error(tr("missing") + ": " + str(exc)); st.stop()

# ---------- 1. Rain ----------
with st.container(border=True):
    st.subheader(tr("rain"))
    rain = pd.DataFrame({"median": [1060, 986, 613], "count": [1, 1, 1]}, index=YEARS)
    plot_years(rain, "mm", COLORS["rain"], show_count=False)
    st.caption(tr("rain_note") + " [KNMI 2023](https://www.knmi.nl/nederland-nu/klimatologie/maand-en-seizoensoverzichten/2023/jaar) · [2024](https://www.knmi.nl/nederland-nu/klimatologie/maand-en-seizoensoverzichten/2024/jaar) · [2025](https://www.knmi.nl/nederland-nu/klimatologie/maand-en-seizoensoverzichten/2025/jaar)")

# ---------- 2-4. Plant measurements ----------
for metric in ("influent_volume", "oxygen", "ammonium"):
    with st.container(border=True):
        st.subheader(tr("volume" if metric == "influent_volume" else metric))
        show_measurement(point_catalog, readings, metric)

# ---------- 5. Electricity ----------
with st.container(border=True):
    st.subheader(tr("electricity"))
    electric = point_catalog.loc[point_catalog.Unit.fillna("").str.casefold().eq("kwh")].drop_duplicates("MeasurementPointID")
    observed = readings.loc[readings.ParsedDate.dt.year.isin(YEARS) & readings.NumericValue.notna()]
    coverage = observed.groupby("MeasurementPointID").ParsedDate.nunique()
    electric = electric.loc[electric.MeasurementPointID.isin(coverage.index)]
    if electric.empty:
        st.info(tr("no_data"))
    else:
        lookup = electric.set_index("MeasurementPointID", drop=False)
        options = lookup.index.astype(str).tolist()
        preferred = max(options, key=lambda item: int(coverage.get(item, 0)))
        point = st.selectbox(tr("point"), options, index=options.index(preferred), format_func=lambda x: fmt_label(lookup.loc[x]), key="electric_point")
        selected = readings.loc[readings.MeasurementPointID.eq(point) & readings.Unit.fillna("").str.casefold().eq("kwh")].copy()
        show_series(selected, str(lookup.loc[point, "Unit"]), "electricity")
    st.caption(tr("elec_note"))

# ---------- Limits and sources ----------
st.info("ℹ️ " + tr("limits"))
st.caption(tr("sources") + ": [KNMI](https://www.knmi.nl/nederland-nu/klimatologie/maandgegevens) · [Biological treatment research](https://pubmed.ncbi.nlm.nih.gov/36898557/) · [Rainfall and plant processes](https://doi.org/10.1016/j.jenvman.2025.126385)")
