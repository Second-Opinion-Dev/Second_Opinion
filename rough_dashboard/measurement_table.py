"""Render the local measurement grid as an escaped, read-only Z-info-style table."""
from html import escape

import pandas as pd


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
