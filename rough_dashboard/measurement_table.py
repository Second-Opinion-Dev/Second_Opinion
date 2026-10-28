"""Render the local measurement grid as an escaped, read-only Z-info-style table."""
from html import escape

import pandas as pd


def scored_measurement_table(records: pd.DataFrame, start, end, *, dutch=False, dark=False) -> str:
    """Render precomputed results by series/day, keeping repeated source rows separate."""
    data = records.loc[records["date"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    context = ["ProcessCode", "SubProcessCodeOrigin", "SubProcessDescription", "MeasurementPointID", "Product", "ProductBalance", "InstallationCodeDestination", "SubProcessDestination", "Unit", "metric"]
    for col in context:
        if col not in data: data[col] = ""
    data[context] = data[context].fillna("").astype(str)
    data = data.sort_values(context + ["date", "source_file", "source_row"], kind="stable")
    data["occurrence"] = data.groupby(context + ["date"], sort=False, dropna=False).cumcount()
    days = pd.date_range(start, end)
    fg, background, stripe, line, head, group, amber, muted = (
        ("#eff7fb", "#172d3c", "#213b4c", "#476174", "#244254", "#315574", "#a66418", "#a8bac4") if dark else
        ("#263a47", "#ffffff", "#f1f4f6", "#d5dde3", "#f8fafb", "#c6d8eb", "#ffb347", "#778995")
    )
    title = "Meetpunt / Deelproces" if dutch else "Measurement point / Subprocess"
    unit = "Eenheid" if dutch else "Unit"
    tooltip = "Gemeld door Isolation Forest; controleer de meting" if dutch else "Flagged by Isolation Forest; review the reading"
    unknown = "Niet beoordeeld" if dutch else "Not assessed"
    parts = [f'''<style>
.result-frame {{overflow:auto;max-height:65vh;background:{background};border:1px solid {line};}}
.result-table {{border-collapse:collapse;width:100%;min-width:1050px;font:14px "Segoe UI",Arial,sans-serif;color:{fg};}}
.result-table th,.result-table td {{padding:5px 8px;border:1px solid {line};white-space:nowrap;}}
.result-table th {{position:sticky;top:0;background:{head};z-index:1;text-align:left;}}
.result-table th.day {{min-width:105px;text-align:center;}}
.result-table td.day {{text-align:right;font-variant-numeric:tabular-nums;}}
.result-table tr.measure:nth-child(even) {{background:{stripe};}}
.result-table tr.process td {{background:{group};font-weight:600;}}
.result-table td.flag {{background:{amber};font-weight:700;}}
.result-table td.unassessed {{color:{muted};}}
.result-table .point-code {{color:{muted};font-size:12px;margin-left:6px;}}
</style><div class="result-frame"><table class="result-table"><thead><tr><th>{escape(title)}</th><th>{escape(unit)}</th>''']
    weekdays = ["ma", "di", "wo", "do", "vr", "za", "zo"] if dutch else ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for day in days:
        parts.append(f'<th class="day">{weekdays[day.weekday()]} {day.day}-{day.month}-{day.year}</th>')
    parts.append("</tr></thead><tbody>")
    previous = None
    for key, rows in data.groupby(context + ["occurrence"], sort=False, dropna=False):
        process = (key[0], key[2])
        if process != previous:
            name = " · ".join(x for x in process if x) or ("Overig" if dutch else "Other")
            parts.append(f'<tr class="process"><td colspan="{len(days)+2}">▾ &nbsp; {escape(name)}</td></tr>')
            previous = process
        first = rows.iloc[0]
        desc = first.get("ParameterDescription")
        if pd.isna(desc) or not str(desc).strip() or str(desc).strip().casefold() == "niet van toepassing":
            desc = first.get("QuantityDescription", "")
        metric_names = {"influent_volume": "Influentvolume" if dutch else "Influent volume", "oxygen": "Zuurstof" if dutch else "Oxygen", "ammonium": "Ammonium", "temperature": "Temperatuur" if dutch else "Temperature", "nitrate": "Nitraat" if dutch else "Nitrate", "suspended_solids": "Zwevende stoffen" if dutch else "Suspended solids"}
        metric_name = metric_names.get(first["metric"], "")
        name = escape(metric_name or str(desc)) if metric_name or (pd.notna(desc) and str(desc).strip()) else escape(str(first["MeasurementPointID"]))
        point = escape(str(first["MeasurementPointID"]))
        repeat = f" ({key[-1]+1})" if key[-1] else ""
        parts.append(f'<tr class="measure"><td>{name}{repeat}<span class="point-code">{point}</span></td><td>{escape(str(first["Unit"]))}</td>')
        lookup = {row.date: row for _,row in rows.iterrows()}
        for day in days:
            row = lookup.get(day)
            if row is None or pd.isna(row.parsed_value):
                parts.append('<td class="day">—</td>'); continue
            value = escape(str(row.get("Value", row.parsed_value)))
            flag = row.forest_flag
            cls = "unassessed" if flag is None or pd.isna(flag) else "flag" if bool(flag) else ""
            tip = ("Gesimuleerde melding; geen model uitgevoerd" if dutch else "Simulated flag; no model was run") if cls == "flag" and row.get("source_file") == "SYNTHETIC DEMO" else tooltip if cls == "flag" else unknown if cls == "unassessed" else ""
            parts.append(f'<td class="day {cls}" title="{escape(tip)}">{value}</td>')
        parts.append("</tr>")
    parts.append("</tbody></table></div>")
    return "".join(parts)


def measurement_table(grid: pd.DataFrame, installation: str, *, dark: bool = False, dutch: bool = False, font_size: int = 14) -> str:
    def safe(value):
        return "" if pd.isna(value) else escape(str(value), quote=True)

    days = [column for column in grid.columns if len(column) == 10 and column[4] == "-"]
    name = "Meetpunt / Deelproces" if dutch else "Measurement point / Subprocess"
    unit = "Eenheid" if dutch else "Unit"
    group_color = "#344e69" if dark else "#c4d5e9"
    background, foreground, striped, lines, heading = (
        ("#192b3b", "#f0f4f8", "#253a4b", "#4a6073", "#263d52") if dark
        else ("#ffffff", "#30383d", "#f1f1f1", "#dfe2e5", "#fafafa")
    )
    html = [f"""<style>
.zi-frame {{ overflow:auto; max-height: 67vh; border:1px solid {lines}; background:{background}; }}
.zi-table {{ border-collapse:collapse; font-family:"Segoe UI",Calibri,sans-serif; font-size:{font_size}px; color:{foreground}; width:100%; min-width:1100px; }}
.zi-table th, .zi-table td {{ border:1px solid {lines}; padding:4px 7px; height:25px; white-space:nowrap; }}
.zi-table th {{ background:{heading}; position:sticky; top:0; z-index:1; text-align:left; font-weight:bold; }}
.zi-table th.date {{ text-align:center; min-width:100px; }}
.zi-table td.date {{ text-align:right; font-variant-numeric:tabular-nums; }}
.zi-table tr.measure:nth-child(even) {{ background:{striped}; }}
.zi-table tr.group td {{ background:{group_color}; font-weight:bold; color:{foreground}; }}
.zi-table td.point {{ min-width:260px; }}
.zi-table .secondary {{ color:{'#c5d7e5' if dark else '#657681'}; font-size:.9em; margin-left:6px; }}
</style><div class="zi-frame"><table class="zi-table"><thead><tr><th>{escape(name)}</th><th>{escape(unit)}</th>"""]
    for day in days:
        date = pd.Timestamp(day)
        weekdays = ["ma", "di", "wo", "do", "vr", "za", "zo"] if dutch else ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        html.append(f'<th class="date">{weekdays[date.weekday()]} {date.day}-{date.month}-{date.year}</th>')
    html.append("</tr></thead><tbody>")
    previous = None
    for _, row in grid.iterrows():
        group = (row["ProcessCode"], row["SubProcessDescription"])
        if group != previous:
            code, description = group
            title = " · ".join(str(x) for x in (code, description) if pd.notna(x) and str(x).strip())
            html.append(f'<tr class="group"><td colspan="{len(days) + 2}">▾ &nbsp;{safe(title)} &nbsp; <span class="secondary">{safe(installation)}</span></td></tr>')
            previous = group
        description = safe(row["MeasurementObjectDescription"]) or safe(row["MeasurementPointID"])
        identifier = safe(row["MeasurementPointID"])
        repeat = f" ({int(row['Occurrence']) + 1})" if int(row["Occurrence"]) else ""
        html.append(f'<tr class="measure"><td class="point">{description}{repeat} <span class="secondary">{identifier}</span></td><td>{safe(row["Unit"])}</td>')
        for day in days:
            html.append(f'<td class="date">{safe(row[day])}</td>')
        html.append("</tr>")
    html.append("</tbody></table></div>")
    return "".join(html)
