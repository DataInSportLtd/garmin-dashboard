"""
Data In Sport — dark / futuristic theme for the Garmin dashboard.

Palette is derived from datainsport.com. Import and call `inject()` once at the
top of every page, then use `page_header()` / `kpi()` for branded components.
"""

import streamlit as st

# --- Brand palette (from datainsport.com) -----------------------------------
COLORS = {
    "bg": "#07111A",          # deep navy-black (page background)
    "surface": "#0F1E2A",     # card / panel background
    "surface_2": "#15293A",   # raised panel
    "steel": "#2b5672",       # secondary
    "electric": "#116dff",    # accent / links
    "sky": "#4eb7f5",         # accent
    "cyan": "#47C9C9",        # primary futuristic accent
    "orange": "#ff8044",      # highlight / warning
    "red": "#df3131",         # alert
    "text": "#E2E2E2",        # primary text
    "muted": "#8F9BA6",       # muted text
}

# Ordered accent list for charts.
CHART_SEQUENCE = ["#47C9C9", "#4eb7f5", "#116dff", "#ff8044", "#2b5672", "#df3131"]

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

:root {{
  --bg: {COLORS['bg']}; --surface: {COLORS['surface']}; --surface2: {COLORS['surface_2']};
  --cyan: {COLORS['cyan']}; --sky: {COLORS['sky']}; --electric: {COLORS['electric']};
  --orange: {COLORS['orange']}; --text: {COLORS['text']}; --muted: {COLORS['muted']};
}}

html, body, [class*="css"], .stApp {{
  font-family: 'Inter', system-ui, sans-serif;
  background: radial-gradient(1200px 600px at 80% -10%, #0d2233 0%, var(--bg) 55%) fixed;
}}
h1, h2, h3, h4, .dis-title {{ font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.01em; }}

/* Branded page header */
.dis-header {{
  display:flex; align-items:center; gap:16px; margin: 0 0 6px 0;
}}
.dis-header .bar {{
  width:6px; height:46px; border-radius:6px;
  background: linear-gradient(180deg, var(--cyan), var(--electric));
  box-shadow: 0 0 18px rgba(71,201,201,0.6);
}}
.dis-header h1 {{ margin:0; font-size: 2.0rem; font-weight:700; color:#fff; }}
.dis-sub {{ color: var(--muted); font-size: 0.95rem; margin: 0 0 18px 22px; }}

/* KPI cards */
.kpi {{
  background: linear-gradient(160deg, var(--surface2) 0%, var(--surface) 100%);
  border: 1px solid rgba(78,183,245,0.14);
  border-radius: 16px; padding: 16px 18px; height: 100%;
  box-shadow: 0 6px 24px rgba(0,0,0,0.35);
  transition: transform .15s ease, border-color .15s ease;
}}
.kpi:hover {{ transform: translateY(-2px); border-color: rgba(71,201,201,0.5); }}
.kpi .label {{ color: var(--muted); font-size:.74rem; text-transform:uppercase; letter-spacing:.08em; }}
.kpi .value {{ font-family:'Space Grotesk',sans-serif; font-size:1.8rem; font-weight:600; color:#fff; line-height:1.1; margin-top:4px; }}
.kpi .value .unit {{ font-size:.9rem; color:var(--muted); font-weight:500; margin-left:4px; }}
.kpi .delta-up {{ color: var(--cyan); font-size:.8rem; }}
.kpi .delta-down {{ color: var(--orange); font-size:.8rem; }}

/* Streamlit native metric tweaks */
[data-testid="stMetric"] {{
  background: var(--surface); border:1px solid rgba(78,183,245,0.12);
  border-radius:14px; padding:14px 16px;
}}
[data-testid="stMetricValue"] {{ font-family:'Space Grotesk',sans-serif; }}

/* Sidebar */
section[data-testid="stSidebar"] {{ background: #061019; border-right:1px solid rgba(78,183,245,0.10); }}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}
.stTabs [data-baseweb="tab"] {{
  background: var(--surface); border-radius:10px 10px 0 0; padding:8px 16px;
}}
.stTabs [aria-selected="true"] {{ background: var(--surface2); color: var(--cyan); }}

/* Dataframes */
[data-testid="stDataFrame"] {{ border:1px solid rgba(78,183,245,0.12); border-radius:12px; }}

a {{ color: var(--sky); }}
hr {{ border-color: rgba(78,183,245,0.12); }}
</style>
"""


def inject():
    """Inject the brand CSS. Call once near the top of each page."""
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", icon: str = ""):
    """Render a branded page header with the signature gradient bar."""
    st.markdown(
        f"""<div class="dis-header"><div class="bar"></div>
        <h1>{icon} {title}</h1></div>""",
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(f'<div class="dis-sub">{subtitle}</div>', unsafe_allow_html=True)


def kpi(col, label: str, value, unit: str = "", delta: str = ""):
    """Render a branded KPI card into the given column."""
    if value is None or value == "":
        value_html = "—"
    else:
        value_html = f'{value}<span class="unit">{unit}</span>' if unit else f"{value}"
    delta_html = ""
    if delta:
        cls = "delta-up" if not str(delta).startswith("-") else "delta-down"
        delta_html = f'<div class="{cls}">{delta}</div>'
    col.markdown(
        f'<div class="kpi"><div class="label">{label}</div>'
        f'<div class="value">{value_html}</div>{delta_html}</div>',
        unsafe_allow_html=True,
    )


def style_fig(fig, height: int = 320):
    """Apply consistent dark styling to a plotly figure."""
    fig.update_layout(
        height=height,
        margin=dict(t=10, b=0, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text"], family="Inter"),
        colorway=CHART_SEQUENCE,
        legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis=dict(gridcolor="rgba(78,183,245,0.08)"),
        yaxis=dict(gridcolor="rgba(78,183,245,0.08)"),
    )
    return fig
