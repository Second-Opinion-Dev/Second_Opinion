"""Local, history-only operator interface over the team's scored outputs."""
from pathlib import Path
import importlib
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import results
# A Streamlit server started before demo support may retain the old module
# between reruns. Reload it once if the current app needs the new API.
results_mtime = Path(results.__file__).stat().st_mtime_ns
if getattr(results, "_dashboard_mtime", None) != results_mtime or not all(hasattr(results, name) for name in ("DEMO_METRICS", "DEMO_PLANT", "demo_metric")):
    importlib.invalidate_caches()
    importlib.reload(results)
    results._dashboard_mtime = results_mtime
from results import METRICS, DEMO_METRICS, DEMO_PLANT, demo_metric, evidence, filtered_cases, load_metric, notifications, source_fingerprint
from measurement_table import scored_measurement_table

ROOT = Path(__file__).resolve().parents[1]
# Full run of src/pipeline.py, relative to the repository root; the earlier sample ZIP
# layout is still accepted via the sidebar.
DEFAULT_RESULTS = Path("data") / "tai" / "pipeline"


def results_path(text):
    """Resolve a sidebar path; relative paths start at the repository root, not the working directory."""
    path = Path(text).expanduser()
    return path if path.is_absolute() else ROOT / path
st.set_page_config(page_title="Second Opinion", page_icon="💧", layout="wide")

WORDS = {
"daily": ("Dagmetingen", "Daily measurements"), "queue": ("Te controleren gevallen", "Cases to check"),
"explore": ("Bekijk metingen", "Look at measurements"), "assistant": ("Analyseassistent", "Analysis assistant"),
"dry": ("Droogte-inzichten", "Dry-weather insights"), "about": ("Over & overdracht", "About & handover"),
"influent_volume": ("Influentvolume", "Influent volume"), "oxygen": ("Zuurstof", "Oxygen"), "ammonium": ("Ammonium", "Ammonium"),
"temperature": ("Temperatuur", "Temperature"), "nitrate": ("Nitraat", "Nitrate"), "suspended_solids": ("Zwevende stoffen", "Suspended solids"),
"demo_warning": ("Gesimuleerde metingen en meldingen; geen modelresultaten.", "Simulated readings and flags; no model results."),
"demo_hint": ("Voorbeeldinstallatie: NL.07.VOORBEELD", "Example plant: NL.07.VOORBEELD"),
"all_metrics": ("Alle meetgroepen", "All metrics"),
"choose_metric": ("Kies één meetgroep in de zijbalk om meldingen te bekijken: modelscores van verschillende meetgroepen zijn niet vergelijkbaar.", "Choose one metric in the sidebar to view cases: scores from different metrics are not comparable."),
"missing_metrics": ("Geen gegevens in de selectie voor", "No data in this selection for"),
"title": ("Historische metingen en onderzoeksqueue", "Historical measurements and review queue"),
"sample": ("Historische gegevens: voorlopige resultaten voor een beperkte selectie meetpunten. Geen live meldingen of bevestigde fouten.", "Historical data: provisional results for a limited selection of points. No live alerts or confirmed faults."),
"filters": ("Selectie", "Filters"), "results": ("Lokale resultatenmap", "Local results folder"),
"plant": ("Installatie", "Plant"), "metric": ("Meetgroep", "Metric"), "point": ("Meetpunt", "Measurement point"),
"all": ("Alle meetpunten", "All points"), "period": ("Periode", "Date range"),
"unavailable": ("Niet beschikbaar", "Unavailable"), "unassessed": ("Niet beoordeeld", "Not assessed"),
"flagged": ("Gemeld door Isolation Forest", "Flagged by Isolation Forest"), "notflagged": ("Niet gemeld door Isolation Forest", "Not flagged by Isolation Forest"),
"latest": ("Laatste beschikbare meting", "Latest available reading"), "flagcount": ("Modelmeldingen in periode", "Model flags in period"),
"threshold": ("Bedrijfsgrens", "Operational limit"), "limitnote": ("Niet beschikbaar in dit bestand; een modeldrempel is geen bedrijfsgrens.", "Not supplied in these files; a model threshold is not an operational limit."),
"overview": ("Overzicht meetgroepen", "Metric overview"), "openqueue": ("Bekijk meldingen", "View cases"),
"no_records": ("Geen metingen beschikbaar voor deze selectie.", "No readings are available for this selection."),
"no_assessed": ("Geen door het model beoordeelde metingen in deze selectie.", "No model-assessed readings in this selection."),
"no_cases": ("Geen modelmeldingen in deze selectie. Dit bewijst niet dat de situatie veilig is.", "No model flags in this selection. This does not establish that conditions are safe."),
"allstatus": ("Alle statussen", "All statuses"), "status": ("Modelstatus", "Model status"), "historyflag": ("Historische controle", "History check"),
"date": ("Datum", "Date"), "value": ("Waarde", "Value"), "unit": ("Eenheid", "Unit"), "score": ("Modelscore", "Model score"),
"modelscore": ("Hogere score betekent ongebruikelijker volgens dit specifieke model; geen kans op een fout. Vergelijk geen scores tussen meetgroepen.", "A higher score is more unusual for this specific model; it is not a fault probability. Do not compare scores across metrics."),
"queuehelp": ("Eén installatie en meetgroep tegelijk. Volgorde: hoogste modelscore eerst; bij gelijke score nieuwste datum en bronverwijzing. Dit is geen gevaarsclassificatie.", "One plant and metric at a time. Order: highest model score first; ties use most recent date and source provenance. This is not a danger rating."),
"budget": ("Aantal gevallen dat u nu kunt bekijken", "Cases available to review now"), "selected": ("Nu bekijken", "Selected for review"), "deferred": ("Voor later", "Deferred"),
"review": ("Beoordeling", "Review status"), "new": ("Niet beoordeeld", "Not reviewed"), "reviewed": ("Bekeken", "Reviewed"), "session": ("Beoordelingen blijven alleen tijdens deze browsersessie bewaard.", "Review status is kept only for this browser session."),
"case": ("Melding", "Case"), "choose": ("Kies een melding", "Select a case"), "open": ("Open melding", "Open case"),
"why": ("Onderbouwing", "Evidence"), "median": ("Historische mediaan", "Historical median"), "unknown": ("Onbekend", "Unknown"),
"ai_explain": ("De modelscore is gebaseerd op meerdere historische kenmerken. De score geeft geen oorzaak of afzonderlijke bijdrage per kenmerk.", "The model score uses multiple historical features. It does not establish a cause or an individual feature contribution."),
"notification": ("Historische modelmelding", "Historical model flag"), "notifyhelp": ("Dit zijn bestaande resultaten, geen nieuwe live meldingen. Klik op een melding om dezelfde meting te openen.", "These are existing results, not new live alerts. Select a notification to open its exact reading."),
"assistantintro": ("De assistent gebruikt uitsluitend opgeslagen gegevens van de geselecteerde melding. Er wordt geen externe AI-dienst aangeroepen.", "The assistant uses only stored evidence for the selected case. No external AI service is called."),
"chart": ("Meetgeschiedenis", "Measurement history"), "historyline": ("Historische mediaan", "Historical median"),
"chartnote": ("De punten tonen bronmetingen en de vooraf berekende historische mediaan. Ontbrekende dagen worden niet ingevuld.", "Markers show source readings and the precomputed historical median. Missing days are not filled."),
"drytext": ("Niet beschikbaar: in de resultaten ontbreken gekoppelde betrouwbare neerslaggegevens en droog/nat-labels. Voor een vergelijking zijn lokale weerobservaties, passende locaties en tijdvakken nodig; kosten vereisen aanvullende bedrijfsgegevens.", "Unavailable: the results do not contain matched reliable rainfall observations or dry/wet labels. A comparison needs suitable weather data, location and period matching; costs require operational data."),
"abouttext": ("Dit lokale prototype toont uitsluitend influentvolume, zuurstof en ammonium. Het leest vooraf berekende resultaten van drie afzonderlijke Isolation Forest-runs en een historische mediaan/MAD-baseline. De modelbestanden ontbreken in het voorbeeldpakket: er wordt geen nieuwe inferentie uitgevoerd. Hogere AI-score betekent ongebruikelijker; de opgeslagen modelvlag gebruikt de per model op validatiedata bepaalde drempel. Operationele grenzen en bevestigde labels ontbreken. De selectie, eenheden en meetbetekenis moeten met TAI worden bevestigd. Gegevens en resultaten blijven lokaal.", "This local prototype covers influent volume, oxygen and ammonium only. It reads precomputed results from three separate Isolation Forest runs and a historical median/MAD baseline. Model files are absent from the sample: no new inference is performed. A higher AI score means more unusual; the stored flag uses each model's validation-derived threshold. Operational limits and confirmed labels are unavailable. TAI must confirm selection, units and measurement meanings. Data and results stay local."),
"rawsource": ("Bronbestand / rij", "Source file / row"), "nonepoint": ("Geen meetpunten voor deze selectie.", "No points for this selection."),
"rank": ("Volgorde", "Review order"),
"appearance": ("Weergave", "Appearance"), "light": ("Licht", "Light"), "dark": ("Donker", "Dark"),
"days": ("Aantal dagen", "Number of days"),
"legend": ("Oranje: modelmelding · Grijs: niet beoordeeld · Geen symbool: geen modelmelding. Een melding is geen bevestigde fout.", "Orange: model flag · Grey: not assessed · No symbol: no model flag. A flag is not a confirmed fault."),
"tablehelp": ("Kies links een installatie en meetgroep. Elke kolom is een dag; een leeg vak betekent dat geen waarde wordt weergegeven.", "Choose a plant and metric on the left. Each column is a day; a blank cell means no value is displayed."),
"bothelp": ("Open Analyseassistent in de navigatie om historische meldingen en uitleg te bekijken.", "Open Analysis assistant in the navigation to view historical flags and explanations."),
"recent7": ("Laatste 7 dagen", "Last 7 days"), "recent30": ("Laatste 30 dagen", "Last 30 days"),
"entireperiod": ("Hele geselecteerde periode", "Entire selected period"),
"alertwindow": ("Meldingen in de periode", "Flags in the period"),
"alertnone": ("Geen modelmeldingen in deze periode. Dat betekent niet dat alle metingen veilig zijn.", "No model flags in this period. This does not mean all readings are safe."),
"alertlatest": ("Meest recente meldingen uit de geselecteerde periode", "Most recent flags in the selected period"),
"showall": ("Bekijk alle meldingen", "View all flags"),
"alertcount": ("modelmeldingen", "model flags"),
"alertwindowhelp": ("De periode eindigt op de gekozen einddatum, niet op vandaag. Dit zijn historische resultaten.", "The window ends on your selected end date, not today. These are historical results."),
"morealerts": ("Kies een melding om de details te openen", "Choose a flag to open its details"),
"show_table": ("Toon in dagmetingen", "Show in daily measurements"),
"rangehelp": ("Daggegevens: het tijdstip van beschikbaarheid is onbekend.", "Daily records: the time the observation became available is unknown."),
"nocompare": ("Vergelijking tussen installaties valt buiten de huidige scope.", "Cross-plant comparison is outside the current scope."),
"partial": ("Historische gegevens", "Historical data"), "resultsbad": ("Resultaten konden niet worden geladen", "Could not load results"),
"source": ("De meetgroepen en waarden hieronder komen uit de lokale resultaten; dit zijn geen bevestigde storingen.", "The metrics and readings below come from local results; they are not confirmed faults."),
"features": ("Opgeslagen modelkenmerken", "Stored model features"),
"contexts": ("Dit meetpunt heeft meerdere procescontexten. Kies een specifieke melding om de bijbehorende historie te bekijken.", "This point has multiple process contexts. Select a specific case to view its matching history."),
"signed_deviation_log": ("Getransformeerde afwijking van de mediaan", "Transformed deviation from median"),
"day_change_log": ("Getransformeerde verandering sinds vorige dag", "Transformed change since previous day"),
"prior_deviation_log_mean": ("Eerdere gemiddelde afwijking", "Prior mean deviation"),
"relative_level_log": ("Getransformeerde relatieve afwijking", "Transformed relative deviation"),
"is_zero": ("Nul-indicator", "Zero indicator"), "repeat_days_log": ("Getransformeerd aantal herhalingsdagen", "Transformed repeat days"),
}

def tr(key):
    if st.session_state.get("plant") == DEMO_PLANT:
        replacements = {
            "flagged": ("Gesimuleerde melding", "Simulated flag"),
            "notflagged": ("Geen melding", "No flag"),
            "flagcount": ("Meldingen in periode", "Flags in period"),
            "score": ("Voorbeeldvolgorde", "Example ordering"),
            "modelscore": ("Handmatig ingestelde volgorde; geen modelscore.", "Manually assigned ordering; not a model score."),
            "queuehelp": ("Gesimuleerde meldingen; geen modelresultaten.", "Simulated flags; not model results."),
            "ai_explain": ("Dit voorbeeld bevat geen modeluitleg.", "This example has no model explanation."),
            "legend": ("Oranje: gesimuleerde melding.", "Orange: simulated flag."),
            "alertcount": ("meldingen", "flags"),
            "notification": ("Gesimuleerde melding", "Simulated flag"),
            "notifyhelp": ("Gesimuleerde meldingen.", "Simulated flags."),
            "alertnone": ("Geen meldingen in deze periode.", "No flags in this period."),
            "no_cases": ("Geen meldingen in deze selectie.", "No flags in this selection."),
            "assistantintro": ("De assistent toont verzonnen voorbeelden, geen modelresultaten.", "The assistant shows fictional examples, not model results."),
            "chartnote": ("Gesimuleerde meetwaarden en mediaan.", "Simulated readings and median."),
        }
        if key in replacements:
            return replacements[key][0 if st.session_state.get("lang", "Nederlands") == "Nederlands" else 1]
    return WORDS.get(key, (key, key))[0 if st.session_state.get("lang", "Nederlands") == "Nederlands" else 1]


def status(value):
    if value is True: return tr("flagged")
    if value is False: return tr("notflagged")
    return tr("unassessed")


@st.cache_data(show_spinner=False, max_entries=12)
def cached_load(root, metric, fingerprint):
    return load_metric(Path(root), metric)


def case_open(case_id):
    st.session_state["selected_case"] = case_id
    st.session_state["page"] = "queue"
    st.session_state["case_choice_" + st.session_state.metric + st.session_state.plant] = case_id
    st.query_params["case"] = case_id
    st.query_params["metric"] = st.session_state.metric
    st.query_params["plant"] = st.session_state.plant
    if len(st.session_state.period) == 2:
        st.query_params["start"] = str(st.session_state.period[0])
        st.query_params["end"] = str(st.session_state.period[1])


def open_notification(case_id, metric):
    st.session_state.metric = metric
    st.session_state.point = ""
    case_open(case_id)


def show_notification_in_table(metric, point_id, date, earliest):
    day = pd.Timestamp(date).date()
    st.session_state.metric = metric
    st.session_state.point = point_id
    st.session_state.period = (max(earliest, day - pd.Timedelta(days=7)), day)
    st.session_state.display_days = 8
    st.session_state.daily_status = "allstatus"
    st.session_state.page = "daily"
    st.query_params.clear()


def open_assistant():
    st.session_state.page = "assistant"


def open_metric(metric):
    st.session_state.metric = metric
    st.session_state.point = ""
    st.session_state.page = "queue"


def number(value):
    return tr("unknown") if pd.isna(value) else f"{float(value):,.3f}".rstrip("0").rstrip(".")


def show_case(case):
    dutch = st.session_state.lang == "Nederlands"
    st.subheader(tr("case") + " · " + str(case["MeasurementPointID"]))
    st.write(f"**{tr('metric')}:** {tr(case['metric'])} · **{tr('plant')}:** {case['InstallationCodeOrigin']} · **{tr('date')}:** {case['date'].date()}")
    st.write(f"**{tr('value')}:** {number(case['parsed_value'])} {case['Unit']} · **{tr('score')}:** {number(case['ai_score'])}")
    st.write(f"**{tr('median')}:** {number(case['history_median'])} {case['Unit']} · **{tr('threshold')}:** {tr('unavailable')}")
    st.write(f"**{tr('rawsource')}:** {case['source_file']} / {case['source_row']}")
    st.info(evidence(case, dutch=dutch))
    st.caption(tr("ai_explain") + " " + tr("nocompare"))
    if case.get("source_file") != "SYNTHETIC DEMO":
        with st.expander(tr("features")):
            for feature in ("signed_deviation_log", "day_change_log", "prior_deviation_log_mean", "relative_level_log", "is_zero", "repeat_days_log"):
                st.write(f"**{tr(feature)}:** {number(pd.to_numeric(case.get(feature), errors='coerce'))}")
    key = "review_" + case["case_key"]
    st.checkbox(tr("reviewed"), key=key)


def plot_point(frame, point, start, end, case=None):
    data = frame.loc[frame.MeasurementPointID.eq(point) & frame.date.between(pd.Timestamp(start), pd.Timestamp(end))].sort_values("date")
    context_columns = [c for c in ("ProcessCode", "SubProcessCodeOrigin", "Product", "ProductBalance", "InstallationCodeDestination", "SubProcessDestination", "Unit") if c in data]
    if case is not None:
        for column in context_columns:
            value = case.get(column)
            data = data.loc[data[column].isna() if pd.isna(value) else data[column].eq(value).fillna(False)]
    elif len(data[context_columns].fillna("").drop_duplicates()) > 1:
        st.info(tr("contexts")); return
    units = data.Unit.dropna().unique()
    if data.empty or len(units) != 1:
        st.info(tr("no_records")); return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.date, y=data.parsed_value, mode="markers", name=tr("value"), customdata=data.Unit, hovertemplate="%{x|%Y-%m-%d}<br>%{y} %{customdata}<extra></extra>"))
    fig.add_trace(go.Scatter(x=data.date, y=data.history_median, mode="markers", name=tr("median"), connectgaps=False, marker=dict(size=4, color="#55869c")))
    flags = data.loc[data.forest_flag.eq(True)]
    fig.add_trace(go.Scatter(x=flags.date, y=flags.parsed_value, mode="markers", name=tr("flagged"), marker=dict(color="#d96817", size=10, symbol="circle-open", line=dict(width=2))))
    fig.update_layout(height=400, margin=dict(l=15,r=15,t=20,b=20), xaxis_title=tr("date"), yaxis_title=f"{tr('value')} ({units[0]})", legend_orientation="h")
    st.plotly_chart(fig, width="stretch")
    st.caption(tr("chartnote"))


if "lang" not in st.session_state: st.session_state.lang = "Nederlands"
if "page" not in st.session_state: st.session_state.page = "queue" if st.query_params.get("case") else "daily"
if st.session_state.page not in ("daily", "queue", "explore", "assistant"):
    st.session_state.page = "daily"
if "selected_case" not in st.session_state: st.session_state.selected_case = st.query_params.get("case", "")
if "appearance" not in st.session_state: st.session_state.appearance = "light"
if "metric" not in st.session_state and st.query_params.get("metric") in METRICS: st.session_state.metric = st.query_params["metric"]
if "plant" not in st.session_state and st.query_params.get("plant"): st.session_state.plant = st.query_params["plant"]
if "period" not in st.session_state and st.query_params.get("start") and st.query_params.get("end"):
    try:
        start_link, end_link = pd.Timestamp(st.query_params["start"]).date(), pd.Timestamp(st.query_params["end"]).date()
        if start_link <= end_link: st.session_state.period = (start_link, end_link)
    except (ValueError, TypeError):
        pass

is_dark = st.session_state.appearance == "dark"
bg, fg, sidebar, control, heading = ("#112333", "#f0f6fa", "#1b3142", "#233b4d", "#d7edf8") if is_dark else ("#f4f7f9", "#17364a", "#ffffff", "#ffffff", "#164b72")
st.markdown(f"""<style>
.stApp, [data-testid="stMain"], [data-testid="stHeader"]{{background:{bg};color:{fg}}}
.block-container{{padding:3.5rem .6rem 3rem;max-width:none}}
h1,h2,h3,p,label,[data-testid="stCaptionContainer"] p{{color:{fg} !important}}
[data-testid="stSidebar"]{{background:{sidebar};border-right:1px solid #cbdce6}}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p{{color:{'#77d8eb' if is_dark else '#168bb3'} !important;font-weight:700}}
[data-testid="stSidebar"] h3{{font-size:1.1rem !important}}
[data-testid="stSelectbox"] [role="group"], [data-testid="stSelectbox"] input, [data-testid="stSelectbox"] button,
[data-testid="stTextInput"] input, [data-testid="stDateInputField"], [data-testid="stDateInputField"] span,
[data-testid="stNumberInput"] input{{background:{control} !important;color:{fg} !important}}
.bar{{background:#195486;color:#fff;padding:14px 20px;border-radius:5px;font:600 20px 'Segoe UI',sans-serif}}
.sub{{color:#dcecf7;font-size:14px;margin-left:15px}}
.st-key-assistant_widget{{position:fixed;bottom:20px;right:22px;z-index:100;width:auto !important;}}
.st-key-assistant_widget [data-testid="stPopover"] > button{{background:#195486 !important;color:white !important;border-radius:26px;padding:10px 16px;box-shadow:0 3px 12px #0003;font-weight:600}}
.st-key-assistant_widget [data-testid="stPopover"] > button p{{color:white !important}}
[data-testid="stRadio"] [role="radiogroup"]{{gap:4px;flex-wrap:wrap}}
[data-testid="stRadio"] [role="radiogroup"] label{{background:{control};border:1px solid #cad7de;border-radius:4px;padding:4px 10px}}
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked){{background:#1faecc;border-color:#1faecc}}
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) p{{color:white !important}}
[data-testid="stRadio"] [role="radiogroup"] label > div:first-child{{display:none}}
</style>""", unsafe_allow_html=True)
left, right, display = st.columns([5, 1.3, 1.2])
with left: st.markdown(f'<div class="bar">Second Opinion <span class="sub">{tr("title")}</span></div>', unsafe_allow_html=True)
with right: st.selectbox("Taal / Language", ["Nederlands", "English"], key="lang")
with display: st.selectbox(tr("appearance"), ["light", "dark"], format_func=tr, key="appearance")
st.warning(tr("sample"))
st.radio("Navigatie / Navigation", ["daily", "queue", "explore", "assistant"], format_func=tr, key="page", horizontal=True, label_visibility="collapsed")

with st.sidebar:
    st.subheader(tr("filters"))
    root_text = st.text_input(tr("results"), value=DEFAULT_RESULTS.as_posix(), key="results_root")
    root = results_path(root_text)
    fingerprint = source_fingerprint(root)

frames, errors, demo_used = {}, {}, False
for item in METRICS:
    try:
        frames[item] = cached_load(str(root), item, fingerprint)[0]
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as exc:
        errors[item] = str(exc)
        frames[item] = pd.DataFrame(columns=["InstallationCodeOrigin", "MeasurementPointID", "date", "parsed_value", "Unit", "forest_flag", "ai_score", "history_median", "source_file", "source_row", "case_key"])
        if item in DEMO_METRICS:
            frames[item] = demo_metric(item)
            demo_used = True
            if isinstance(exc, FileNotFoundError):
                del errors[item]
if len(errors) == len(METRICS):
    st.error(tr("resultsbad") + ": " + "; ".join(errors.values()))
    st.stop()
if errors:
    st.sidebar.warning(tr("resultsbad") + ": " + ", ".join(tr(m) for m in errors))
if demo_used:  # only when a metric fell back to the fictional example plant
    st.sidebar.caption(tr("demo_hint"))
plants = sorted(set().union(*(set(f.InstallationCodeOrigin.dropna().astype(str)) for f in frames.values())))
if not plants:
    st.info(tr("no_records")); st.stop()
with st.sidebar:
    if st.session_state.get("plant") not in plants: st.session_state.plant = next((p for p in plants if p != DEMO_PLANT), plants[0])
    plant = st.selectbox(tr("plant"), plants, key="plant")
    if plant == DEMO_PLANT:
        st.caption(tr("demo_warning"))
    metric = st.selectbox(tr("metric"), ("all_metrics",) + METRICS, format_func=tr, key="metric")
    source = pd.concat(list(frames.values()), ignore_index=True) if metric == "all_metrics" else frames[metric]
    points = sorted(source.loc[source.InstallationCodeOrigin.eq(plant), "MeasurementPointID"].dropna().astype(str).unique())
    if "point" in st.session_state and st.session_state.point not in [""] + points:
        st.session_state.point = ""
    point = st.selectbox(tr("point"), [""] + points, format_func=lambda x: x or tr("all"), key="point")
    dates = pd.concat([f.date.dropna() for f in frames.values()])
    if dates.empty: st.info(tr("no_records")); st.stop()
    minimum, maximum = dates.min().date(), dates.max().date()
    default_start = max(minimum, pd.Timestamp("2025-01-01").date())
    default_end = min(maximum, pd.Timestamp("2025-12-31").date())
    if default_start > default_end: default_start, default_end = minimum, maximum
    if "period" in st.session_state:
        prior = st.session_state.period
        if len(prior) == 2 and (prior[0] < minimum or prior[1] > maximum):
            st.session_state.period = (default_start, default_end)
    interval = st.date_input(tr("period"), value=(default_start, default_end), min_value=minimum, max_value=maximum, key="period", help=tr("rangehelp"))
if not isinstance(interval, (tuple, list)) or len(interval) != 2:
    st.info(tr("period")); st.stop()
start, end = interval
if plant == DEMO_PLANT:
    st.caption(tr("demo_warning"))
scoped = source.loc[source.InstallationCodeOrigin.eq(plant) & source.date.between(pd.Timestamp(start), pd.Timestamp(end))].copy()
if point: scoped = scoped.loc[scoped.MeasurementPointID.eq(point)]
cases = filtered_cases(source, plant, start, end, point or None) if metric != "all_metrics" else pd.DataFrame()
cases["review_rank"] = range(1, len(cases) + 1)

all_alerts = notifications(frames, plant, start, end, point or None)
recent_start = max(pd.Timestamp(start), pd.Timestamp(end) - pd.Timedelta(days=6))
recent = all_alerts.loc[all_alerts.date.ge(recent_start)] if not all_alerts.empty else all_alerts
with st.container(key="assistant_widget"):
    with st.popover(f"🤖  {tr('assistant')} · {len(recent)}", help=tr("recent7")):
        st.subheader(tr("recent7"))
        st.caption(f"{recent_start.date()} — {end} · {tr('alertwindowhelp')}")
        if recent.empty:
            st.info(tr("alertnone"))
            if not all_alerts.empty:
                st.caption(tr("alertlatest"))
        display_alerts = recent if not recent.empty else all_alerts
        for _, alert in display_alerts.head(5).iterrows():
            label = f"{tr(alert.metric)} · {alert.MeasurementPointID} · {alert.date.date()}"
            st.button(label, key="bot_" + alert.case_key, on_click=show_notification_in_table, args=(alert.metric, alert.MeasurementPointID, alert.date, minimum), width="stretch", help=tr("show_table"))
            st.caption(f"{tr('value')}: {number(alert.parsed_value)} {alert.Unit} · {tr('median')}: {number(alert.history_median)} {alert.Unit}")
            st.button(tr("open"), key="bot_case_" + alert.case_key, on_click=open_notification, args=(alert.case_key, alert.metric))
        if not all_alerts.empty:
            st.button(tr("showall") + f" ({len(all_alerts)})", key="bot_all", on_click=open_assistant)

if metric == "all_metrics" and st.session_state.page in ("queue", "explore"):
    st.info(tr("choose_metric"))
    st.stop()

if st.session_state.page == "daily":
    st.header(tr("daily"))
    st.caption(tr("tablehelp"))
    c1, c2 = st.columns([2, 1])
    status_filter = c1.selectbox(tr("status"), ["allstatus", "flagged", "notflagged", "unassessed"], format_func=tr, key="daily_status")
    days = c2.selectbox(tr("days"), [8, 7, 14, 1], key="display_days")
    view = scoped.copy()
    if status_filter != "allstatus":
        view = view.loc[view.forest_flag.map(status).eq(tr(status_filter))]
    grid_start = max(pd.Timestamp(start), pd.Timestamp(end) - pd.Timedelta(days=days - 1))
    grid_view = view.loc[view.date.between(grid_start, pd.Timestamp(end))]
    if grid_view.empty:
        st.info(tr("no_records"))
    else:
        st.caption(f"{plant} · {tr(metric)} · {grid_start.date()} — {end}")
        if metric == "all_metrics":
            missing_metrics = [m for m in METRICS if m not in set(grid_view["metric"].dropna())]
            if missing_metrics:
                st.caption(tr("missing_metrics") + ": " + ", ".join(tr(m) for m in missing_metrics) + ".")
        st.markdown(scored_measurement_table(grid_view, grid_start, pd.Timestamp(end), dutch=st.session_state.lang == "Nederlands", dark=is_dark), unsafe_allow_html=True)
        st.caption(tr("legend"))
    with st.expander(tr("overview")):
        st.caption(tr("source"))
        columns = st.columns(3)
        for i, m in enumerate(METRICS):
            col = columns[i % len(columns)]
            f = frames[m]
            data = f.loc[f.InstallationCodeOrigin.eq(plant) & f.date.between(pd.Timestamp(start), pd.Timestamp(end))].sort_values("date")
            with col:
                with st.container(border=True):
                    st.subheader(tr(m))
                    if m in errors: st.write(tr("unavailable"))
                    elif data.empty: st.write(tr("no_records"))
                    else:
                        last = data.loc[data.parsed_value.notna()].tail(1)
                        if len(last):
                            row = last.iloc[0]
                            st.write(f"**{tr('latest')}:** {number(row.parsed_value)} {row.Unit} · {row.date.date()} · {row.MeasurementPointID}")
                        assessed = data.forest_flag.notna().any()
                        st.write(f"**{tr('flagcount')}:** {int(data.forest_flag.eq(True).sum()) if assessed else tr('unavailable')}")
                    st.caption(tr("threshold") + ": " + tr("unavailable"))
                    st.button(tr("openqueue"), key="open_"+m, on_click=open_metric, args=(m,))
    st.caption(tr("limitnote") + " " + tr("rangehelp"))

elif st.session_state.page == "queue":
    st.header(tr("queue")); st.caption(tr("queuehelp"))
    if cases.empty: st.info(tr("no_cases"))
    else:
        budget_key = "budget_" + metric + plant
        if budget_key in st.session_state:
            st.session_state[budget_key] = min(st.session_state[budget_key], len(cases))
        budget = st.number_input(tr("budget"), min_value=0, max_value=len(cases), value=min(10,len(cases)), key=budget_key)
        selected, deferred = cases.iloc[:budget], cases.iloc[budget:]
        a,b = st.columns(2); a.metric(tr("selected"), len(selected)); b.metric(tr("deferred"),len(deferred))
        st.caption(tr("modelscore") + " " + tr("session"))
        for name, group in [(tr("selected"),selected),(tr("deferred"),deferred)]:
            st.subheader(name)
            if group.empty: st.caption("—")
            else:
                displayed = group[["review_rank","date","MeasurementPointID","parsed_value","Unit","ai_score","case_key"]].copy()
                displayed[tr("status")] = tr("flagged")
                displayed[tr("review")] = displayed.case_key.map(lambda x: tr("reviewed") if st.session_state.get("review_"+x) else tr("new"))
                displayed = displayed.rename(columns={"review_rank":tr("rank"),"date":tr("date"),"MeasurementPointID":tr("point"),"parsed_value":tr("value"),"Unit":tr("unit"),"ai_score":tr("score"),"case_key":"ID"})
                table_key = "table_"+metric+plant+name
                selection = st.dataframe(displayed, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key=table_key)
                chosen_rows = selection.selection.rows
                marker = "last_" + table_key
                if chosen_rows and st.session_state.get(marker) != (chosen_rows[0], group.iloc[chosen_rows[0]].case_key):
                    chosen_id = group.iloc[chosen_rows[0]].case_key
                    st.session_state[marker] = (chosen_rows[0], chosen_id)
                    st.session_state.selected_case = chosen_id
                    st.session_state["case_choice_"+metric+plant] = chosen_id
                elif not chosen_rows:
                    st.session_state.pop(marker, None)
        ids = cases.case_key.tolist()
        requested = st.session_state.get("selected_case", "")
        index = ids.index(requested) if requested in ids else 0
        case_id = st.selectbox(tr("choose"), ids, index=index, format_func=lambda x: f"{cases.loc[cases.case_key.eq(x),'MeasurementPointID'].iloc[0]} · {cases.loc[cases.case_key.eq(x),'date'].iloc[0].date()} · {x[:8]}", key="case_choice_"+metric+plant)
        st.session_state.selected_case = case_id
        case = cases.loc[cases.case_key.eq(case_id)].iloc[0]
        show_case(case)
        plot_point(source.loc[source.InstallationCodeOrigin.eq(plant)], case.MeasurementPointID, max(start,(case.date-pd.Timedelta(days=90)).date()), case.date.date(), case=case)

elif st.session_state.page == "explore":
    st.header(tr("explore"))
    if not points: st.info(tr("nonepoint"))
    else:
        chosen = st.selectbox(tr("point"), points, index=points.index(point) if point in points else 0, key="chart_point")
        plot_point(source.loc[source.InstallationCodeOrigin.eq(plant)], chosen, start, end)
        st.caption(tr("limitnote") + " " + tr("nocompare"))

elif st.session_state.page == "assistant":
    st.header(tr("assistant")); st.write(tr("assistantintro")); st.caption(tr("alertwindowhelp"))
    window = st.radio(tr("alertwindow"), ["recent7", "recent30", "entireperiod"], format_func=tr, horizontal=True, key="assistant_window")
    window_start = pd.Timestamp(start) if window == "entireperiod" else max(pd.Timestamp(start), pd.Timestamp(end) - pd.Timedelta(days=6 if window == "recent7" else 29))
    visible = all_alerts.loc[all_alerts.date.ge(window_start)] if not all_alerts.empty else all_alerts
    st.caption(f"{plant} · {window_start.date()} — {end} · {len(visible)} {tr('alertcount')}")
    if visible.empty:
        st.info(tr("alertnone"))
    else:
        st.caption(tr("notifyhelp"))
        for _, row in visible.head(10).iterrows():
            label = f"{tr(row.metric)} · {row.MeasurementPointID} · {row.date.date()}"
            st.button(label, key="notification_"+row.case_key, width="stretch", on_click=show_notification_in_table, args=(row.metric, row.MeasurementPointID, row.date, minimum), help=tr("show_table"))
            st.caption(f"{tr('value')}: {number(row.parsed_value)} {row.Unit} · {tr('median')}: {number(row.history_median)} {row.Unit}")
            st.button(tr("open"), key="case_notification_"+row.case_key, on_click=open_notification, args=(row.case_key, row.metric))
        if len(visible) > 10:
            ids = visible.case_key.tolist()
            selected_alert = st.selectbox(tr("morealerts"), ids, format_func=lambda x: f"{tr(visible.loc[visible.case_key.eq(x),'metric'].iloc[0])} · {visible.loc[visible.case_key.eq(x),'MeasurementPointID'].iloc[0]} · {visible.loc[visible.case_key.eq(x),'date'].iloc[0].date()}")
            selected_metric = visible.loc[visible.case_key.eq(selected_alert), "metric"].iloc[0]
            st.button(tr("open"), on_click=open_notification, args=(selected_alert, selected_metric))
        st.caption(tr("limitnote"))

st.divider(); st.caption(tr("partial") + " · " + tr("rangehelp"))
