# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Planta F — Control de Operaciones
# Autor: generado con Claude (Anthropic)
# Stack: Python · Dash · Plotly · Pandas
# Principios de visualización: Edward Tufte (Data-Ink Ratio) · Stephen Few
# KPIs documentados bajo metodología SMART
#
# Instalación:
#   pip install dash pandas openpyxl
#
# Uso:
#   python app.py
#   Abrir en navegador: http://127.0.0.1:8050
# ─────────────────────────────────────────────────────────────────────────────

import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc

# ── CONSTANTES ────────────────────────────────────────────────────────────────
TURNO_MIN   = 480   # minutos por turno estándar
CICLO_IDEAL = 4.0   # tiempo de ciclo ideal (min/unidad)
EXCEL_PATH  = "plantaf.xlsx"

# Paleta industrial oscura (Tufte: fondo neutro, color solo donde importa)
COLORS = dict(
    bg0     = "#080b0f",
    bg1     = "#0e1318",
    bg2     = "#141b22",
    bg3     = "#1c2530",
    border  = "#232e3c",
    amber   = "#f5a623",
    teal    = "#2dd4bf",
    red     = "#f87171",
    green   = "#4ade80",
    blue    = "#60a5fa",
    text    = "#e8edf3",
    text2   = "#8a9bb0",
    textdim = "#4a5a6b",
)

PLOTLY_LAYOUT = dict(
    paper_bgcolor = "rgba(0,0,0,0)",
    plot_bgcolor  = "rgba(0,0,0,0)",
    font          = dict(family="monospace", color=COLORS["text2"], size=10),
    margin        = dict(l=40, r=16, t=10, b=40),
    showlegend    = True,
    legend        = dict(
        bgcolor     = "rgba(0,0,0,0)",
        font        = dict(size=9, color=COLORS["text2"]),
        orientation = "h",
        x=0, y=1.12,
    ),
    xaxis = dict(
        showgrid     = False,
        zeroline     = False,
        showline     = False,
        tickfont     = dict(size=9),
    ),
    yaxis = dict(
        gridcolor = "#141b22",
        gridwidth = 1,
        zeroline  = False,
        showline  = False,
        tickfont  = dict(size=9),
    ),
)

# ── SMART DEFINITIONS ─────────────────────────────────────────────────────────
SMART = {
    "oee": {
        "nombre": "OEE — Efectividad Global del Equipo",
        "S": "Medir la eficiencia productiva combinando disponibilidad, rendimiento y calidad de cada línea.",
        "M": "OEE = Disponibilidad × Performance × Calidad. Meta: ≥ 85% (clase mundial).",
        "A": "Benchmarks del sector; las líneas actuales operan en rango 82–92%.",
        "R": "KPI núcleo de manufactura. Su mejora impacta capacidad, costo y satisfacción.",
        "T": "Evaluación mensual; objetivo de mejora +2 pp por trimestre.",
        "formula": "OEE = Disponibilidad × Performance × Calidad",
    },
    "fpy": {
        "nombre": "FPY — First Pass Yield",
        "S": "Cuantificar la proporción de unidades que pasan sin defectos en la primera pasada.",
        "M": "FPY = (Producidas − Defectos) / Producidas × 100%. Meta: ≥ 97%.",
        "A": "Promedio actual supera 96%; ajustes en horno proyectan alcanzar 97.5%.",
        "R": "Reduce costos de retrabajo y scrap; mejora el tiempo de ciclo efectivo.",
        "T": "Revisión semanal; acción si cae bajo 95% por más de 3 días.",
        "formula": "FPY = (Producidas − Defectos) / Producidas",
    },
    "defectos": {
        "nombre": "Tasa de Defectos",
        "S": "Medir la proporción de unidades defectuosas para identificar líneas y turnos críticos.",
        "M": "Tasa = Defectos / Producidas × 100%. Meta: ≤ 3%.",
        "A": "Media histórica ~3.2%; con SPC en horno se puede reducir a 2.5%.",
        "R": "Impacta costo de calidad, satisfacción del cliente y eficiencia de línea.",
        "T": "Control diario; análisis Pareto mensual de causas raíz.",
        "formula": "Tasa = Defectos / Unidades_producidas × 100",
    },
    "disponibilidad": {
        "nombre": "Disponibilidad",
        "S": "Medir el tiempo efectivo de operación respecto al tiempo programado.",
        "M": "Disponibilidad = (480 − Paros_min) / 480 × 100%. Meta: ≥ 95%.",
        "A": "Valor actual ~97.5%; mantenimiento preventivo puede sostenerlo sobre 96%.",
        "R": "Los paros no planificados son la causa #1 de pérdida de OEE.",
        "T": "Monitoreo por turno; escalación si supera 30 min de paro.",
        "formula": "Disponib. = (480 − Paros_min) / 480",
    },
    "entrega": {
        "nombre": "Entregas a Tiempo (OTD)",
        "S": "Medir la proporción de turnos en que la producción se completó a tiempo.",
        "M": "OTD = Turnos_a_tiempo / Total_turnos × 100%. Meta: ≥ 90%.",
        "A": "Histórico ~88%; con mejor planificación se alcanza 90%.",
        "R": "Afecta directamente el nivel de servicio al cliente.",
        "T": "Reporte diario; revisión de causas si baja de 85% en cualquier semana.",
        "formula": "OTD = Σ(a_tiempo=1) / Total_registros × 100",
    },
    "margen": {
        "nombre": "Margen Bruto",
        "S": "Cuantificar la rentabilidad por unidad producida.",
        "M": "Margen = (Precio_venta − Costo_unit) / Precio_venta × 100%. Meta: ≥ 25%.",
        "A": "Margen actual ~26%; controlar retrabajo puede mejorar 1–2 pp.",
        "R": "Conecta eficiencia operativa con resultados económicos.",
        "T": "Análisis mensual por producto y línea.",
        "formula": "Margen = (Precio_venta − Costo_unit) / Precio_venta",
    },
    "ciclo": {
        "nombre": "Tiempo de Ciclo",
        "S": "Monitorear el tiempo promedio por unidad para detectar desviaciones del estándar 4.0 min.",
        "M": "Promedio en minutos. Meta: ≤ 4.5 min/unidad. Alerta: > 5 min.",
        "A": "Mínimo observado 4.0 min; meta de 4.3 min es alcanzable con entrenamiento.",
        "R": "Determina la capacidad máxima de la línea y el componente Performance del OEE.",
        "T": "Seguimiento por turno; análisis de varianza semanal.",
        "formula": "Performance = Ciclo_ideal(4.0) / Ciclo_real",
    },
    "paros": {
        "nombre": "Paros (Downtime)",
        "S": "Minimizar los minutos de paro no planificado por turno.",
        "M": "Promedio de minutos de paro por turno. Meta: ≤ 8 min/turno.",
        "A": "Promedio actual ~11.8 min; mantenimiento predictivo apunta a reducir 30%.",
        "R": "El downtime es la principal pérdida en OEE.",
        "T": "Registro en tiempo real; análisis Pareto mensual por tipo de falla.",
        "formula": "Disponib. = (480 − Paros_min) / 480 × 100",
    },
    "horas_extra": {
        "nombre": "Horas Extra Promedio",
        "S": "Controlar las horas extra como indicador de sobrecarga y planeación deficiente.",
        "M": "Promedio de horas extra por turno. Meta: ≤ 0.8 h/turno.",
        "A": "Promedio actual ~1.0 h; mejor planificación reduce al objetivo.",
        "R": "Las horas extra incrementan el costo laboral.",
        "T": "Control semanal; escalación si supera 1.5 h/turno por más de 3 días.",
        "formula": "Σ(horas_extra) / N_turnos",
    },
    "retrabajo": {
        "nombre": "% Retrabajo",
        "S": "Determinar la fracción de unidades que requieren reprocesamiento.",
        "M": "% Retrabajo = Retrabajadas / Producidas × 100%. Meta: ≤ 1.5%.",
        "A": "Histórico actual ~1.0%; estandarización de operadores nuevos apunta a 0.8%.",
        "R": "El retrabajo consume capacidad y aumenta el costo unitario.",
        "T": "Revisión por turno; benchmarking trimestral entre operadores.",
        "formula": "% Retrabajo = Retrabajadas / Producidas × 100",
    },
}

# ── CARGA Y PREPROCESAMIENTO ──────────────────────────────────────────────────
def cargar_datos(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["mes"]   = df["fecha"].dt.to_period("M").astype(str)
    df["mes_label"] = df["fecha"].dt.strftime("%b %Y")

    # KPIs derivados
    df["tasa_defectos"]  = df["defectos"] / df["unidades_producidas"]
    df["fpy"]            = 1 - df["tasa_defectos"]
    df["margen"]         = (df["precio_venta"] - df["costo_unitario"]) / df["precio_venta"]
    df["retrabajo_pct"]  = df["retrabajo_unidades"] / df["unidades_producidas"]
    df["disponibilidad"] = ((TURNO_MIN - df["paros_min"]) / TURNO_MIN).clip(0, 1)
    df["performance"]    = (CICLO_IDEAL / df["tiempo_ciclo_min"]).clip(0, 1)
    df["calidad"]        = df["fpy"]
    df["oee"]            = df["disponibilidad"] * df["performance"] * df["calidad"]
    return df

DF = cargar_datos(EXCEL_PATH)

# ── APP ───────────────────────────────────────────────────────────────────────
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Planta F — OPS Control",
)
server = app.server  # Necesario para gunicorn en Render

# ── HELPERS DE ESTILO ─────────────────────────────────────────────────────────
def card_style(accent=None):
    return {
        "background": COLORS["bg2"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "6px",
        "padding": "16px",
        "borderTop": f"2px solid {accent or COLORS['amber']}",
    }

def kpi_delta_color(condition):
    return COLORS["green"] if condition else COLORS["red"]

def fmt_pct(v): return f"{v*100:.1f}%"
def fmt1(v):    return f"{v:.1f}"
def fmt2(v):    return f"{v:.2f}"

# ── MODAL SMART ───────────────────────────────────────────────────────────────
def make_modal(kpi_id):
    info = SMART.get(kpi_id, {})
    if not info:
        return html.Div()

    def row(letra, palabra, texto, color=COLORS["amber"]):
        return html.Div([
            html.Div([
                html.Span(letra, style={"fontSize": "22px", "fontWeight": "700",
                                        "color": color, "fontFamily": "monospace"}),
                html.Div(palabra, style={"fontSize": "9px", "color": COLORS["textdim"],
                                         "textTransform": "uppercase", "letterSpacing": "0.1em"}),
            ], style={"marginBottom": "6px"}),
            html.Div(texto, style={"fontSize": "12px", "color": COLORS["text2"], "lineHeight": "1.5"}),
        ], style={"background": COLORS["bg3"], "border": f"1px solid {COLORS['border']}",
                  "borderRadius": "4px", "padding": "12px", "marginBottom": "8px"})

    return dbc.Modal([
        dbc.ModalHeader(
            html.Div([
                html.Div(info["nombre"], style={"color": COLORS["amber"], "fontWeight": "700",
                                                 "fontFamily": "monospace", "fontSize": "15px"}),
                html.Div("OBJETIVO SMART", style={"fontSize": "10px", "color": COLORS["textdim"],
                                                   "fontFamily": "monospace"}),
            ]),
            style={"background": COLORS["bg2"], "borderBottom": f"1px solid {COLORS['border']}"},
            close_button=True,
        ),
        dbc.ModalBody([
            row("S", "Specific",    info["S"]),
            row("M", "Measurable",  info["M"]),
            row("A", "Achievable",  info["A"]),
            row("R", "Relevant",    info["R"]),
            row("T", "Time-bound",  info["T"]),
            html.Div("FÓRMULA", style={"fontSize": "10px", "color": COLORS["textdim"],
                                        "textTransform": "uppercase", "letterSpacing": "0.08em",
                                        "marginTop": "12px", "marginBottom": "6px"}),
            html.Div(info["formula"], style={
                "background": COLORS["bg3"], "border": f"1px solid {COLORS['border']}",
                "borderRadius": "4px", "padding": "10px 14px",
                "fontFamily": "monospace", "fontSize": "12px", "color": COLORS["teal"],
            }),
        ], style={"background": COLORS["bg2"]}),
    ],
        id=f"modal-{kpi_id}",
        is_open=False,
        style={"fontFamily": "monospace"},
        contentClassName="border-0",
    )

# ── LAYOUT ────────────────────────────────────────────────────────────────────
app.layout = html.Div([

    # ── HEADER ────────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.Div("PF", style={
                "width": "36px", "height": "36px", "background": COLORS["amber"],
                "clipPath": "polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%)",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "fontFamily": "monospace", "fontWeight": "700", "fontSize": "11px", "color": "#000",
            }),
            html.Div([
                html.Div("PLANTA F — OPS CONTROL",
                         style={"fontFamily": "monospace", "fontWeight": "600",
                                "fontSize": "13px", "color": COLORS["text"], "letterSpacing": "0.05em"}),
                html.Div("Manufacturing Intelligence Dashboard · 2024–2025",
                         style={"fontSize": "10px", "color": COLORS["textdim"]}),
            ], style={"marginLeft": "12px"}),
        ], style={"display": "flex", "alignItems": "center"}),
        html.Div([
            html.Div([
                html.Div(style={"width": "7px", "height": "7px", "background": COLORS["green"],
                                "borderRadius": "50%", "marginRight": "6px",
                                "animation": "pulse 2s infinite"}),
                "EN LÍNEA",
            ], style={"display": "flex", "alignItems": "center", "fontFamily": "monospace",
                      "fontSize": "10px", "color": COLORS["green"], "border": f"1px solid #14532d",
                      "padding": "3px 10px", "borderRadius": "20px"}),
        ]),
    ], style={
        "background": COLORS["bg1"], "borderBottom": f"1px solid {COLORS['border']}",
        "padding": "0 24px", "height": "56px", "display": "flex",
        "alignItems": "center", "justifyContent": "space-between",
        "position": "sticky", "top": "0", "zIndex": "100",
    }),

    # ── FILTROS ───────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.Span("Desde", style={"fontSize": "10px", "color": COLORS["textdim"],
                                       "fontFamily": "monospace", "marginRight": "8px"}),
            dcc.DatePickerSingle(id="f-desde", date="2024-01-01",
                                 display_format="YYYY-MM-DD",
                                 style={"fontFamily": "monospace"}),
        ], style={"display": "flex", "alignItems": "center", "marginRight": "16px"}),
        html.Div([
            html.Span("Hasta", style={"fontSize": "10px", "color": COLORS["textdim"],
                                       "fontFamily": "monospace", "marginRight": "8px"}),
            dcc.DatePickerSingle(id="f-hasta", date="2025-12-31",
                                 display_format="YYYY-MM-DD",
                                 style={"fontFamily": "monospace"}),
        ], style={"display": "flex", "alignItems": "center", "marginRight": "16px"}),
        html.Div([
            html.Span("Línea", style={"fontSize": "10px", "color": COLORS["textdim"],
                                       "fontFamily": "monospace", "marginRight": "8px"}),
            dcc.Dropdown(id="f-linea",
                         options=[{"label": "Todas", "value": ""}] +
                                 [{"label": l, "value": l} for l in ["L1", "L2", "L3"]],
                         value="", clearable=False,
                         style={"width": "90px", "fontFamily": "monospace", "fontSize": "11px"}),
        ], style={"display": "flex", "alignItems": "center", "marginRight": "16px"}),
        html.Div([
            html.Span("Turno", style={"fontSize": "10px", "color": COLORS["textdim"],
                                       "fontFamily": "monospace", "marginRight": "8px"}),
            dcc.Dropdown(id="f-turno",
                         options=[{"label": "Todos", "value": ""}] +
                                 [{"label": t, "value": t} for t in ["Matutino", "Vespertino", "Nocturno"]],
                         value="", clearable=False,
                         style={"width": "120px", "fontFamily": "monospace", "fontSize": "11px"}),
        ], style={"display": "flex", "alignItems": "center", "marginRight": "16px"}),
        html.Div([
            html.Span("Producto", style={"fontSize": "10px", "color": COLORS["textdim"],
                                          "fontFamily": "monospace", "marginRight": "8px"}),
            dcc.Dropdown(id="f-producto",
                         options=[{"label": "Todos", "value": ""}] +
                                 [{"label": p, "value": p} for p in ["Producto A", "Producto B", "Producto C"]],
                         value="", clearable=False,
                         style={"width": "130px", "fontFamily": "monospace", "fontSize": "11px"}),
        ], style={"display": "flex", "alignItems": "center"}),
        html.Div(id="rec-count", style={
            "marginLeft": "auto", "fontFamily": "monospace",
            "fontSize": "10px", "color": COLORS["textdim"],
        }),
    ], style={
        "background": COLORS["bg1"], "borderBottom": f"1px solid {COLORS['border']}",
        "padding": "10px 24px", "display": "flex", "flexWrap": "wrap",
        "alignItems": "center", "gap": "8px",
    }),

    # ── CONTENIDO PRINCIPAL ───────────────────────────────────────────────────
    html.Div([

        # KPI Cards
        html.Div(id="kpi-cards", style={
            "display": "grid",
            "gridTemplateColumns": "repeat(auto-fill, minmax(180px, 1fr))",
            "gap": "12px", "marginBottom": "20px",
        }),

        # Fila 1: Gauge + Producción mensual
        html.Div([
            html.Div([
                html.Div("● OEE GLOBAL", style={"fontSize": "10px", "fontFamily": "monospace",
                                                  "color": COLORS["textdim"], "marginBottom": "12px",
                                                  "textTransform": "uppercase", "letterSpacing": "0.08em"}),
                dcc.Graph(id="g-gauge", config={"displayModeBar": False},
                          style={"height": "260px"}),
            ], style={**card_style(COLORS["amber"]), "flex": "1", "minWidth": "220px"}),

            html.Div([
                html.Div("● PRODUCCIÓN MENSUAL & OEE", style={"fontSize": "10px", "fontFamily": "monospace",
                                                               "color": COLORS["textdim"], "marginBottom": "12px",
                                                               "textTransform": "uppercase", "letterSpacing": "0.08em"}),
                dcc.Graph(id="g-prod", config={"displayModeBar": False},
                          style={"height": "260px"}),
            ], style={**card_style(COLORS["teal"]), "flex": "2", "minWidth": "300px"}),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px", "flexWrap": "wrap"}),

        # Fila 2: Defectos + Turnos
        html.Div([
            html.Div([
                html.Div("● DEFECTOS POR LÍNEA Y TURNO", style={"fontSize": "10px", "fontFamily": "monospace",
                                                                  "color": COLORS["textdim"], "marginBottom": "12px",
                                                                  "textTransform": "uppercase", "letterSpacing": "0.08em"}),
                dcc.Graph(id="g-defectos", config={"displayModeBar": False},
                          style={"height": "220px"}),
            ], style={**card_style(COLORS["red"]), "flex": "2", "minWidth": "300px"}),

            html.Div([
                html.Div("● DISTRIBUCIÓN POR TURNO", style={"fontSize": "10px", "fontFamily": "monospace",
                                                              "color": COLORS["textdim"], "marginBottom": "12px",
                                                              "textTransform": "uppercase", "letterSpacing": "0.08em"}),
                dcc.Graph(id="g-turnos", config={"displayModeBar": False},
                          style={"height": "220px"}),
            ], style={**card_style(COLORS["blue"]), "flex": "1", "minWidth": "220px"}),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px", "flexWrap": "wrap"}),

        # Fila 3: Margen + Paros
        html.Div([
            html.Div([
                html.Div("● MARGEN BRUTO VS ENTREGAS A TIEMPO (mensual)", style={
                    "fontSize": "10px", "fontFamily": "monospace", "color": COLORS["textdim"],
                    "marginBottom": "12px", "textTransform": "uppercase", "letterSpacing": "0.08em"}),
                dcc.Graph(id="g-margen", config={"displayModeBar": False},
                          style={"height": "220px"}),
            ], style={**card_style(COLORS["green"]), "flex": "2", "minWidth": "300px"}),

            html.Div([
                html.Div("● PAROS & HORAS EXTRA (mensual)", style={
                    "fontSize": "10px", "fontFamily": "monospace", "color": COLORS["textdim"],
                    "marginBottom": "12px", "textTransform": "uppercase", "letterSpacing": "0.08em"}),
                dcc.Graph(id="g-paros", config={"displayModeBar": False},
                          style={"height": "220px"}),
            ], style={**card_style(COLORS["amber"]), "flex": "1", "minWidth": "220px"}),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px", "flexWrap": "wrap"}),

        # Ranking operadores
        html.Div([
            html.Div("● RANKING DE OPERADORES", style={"fontSize": "10px", "fontFamily": "monospace",
                                                        "color": COLORS["textdim"], "marginBottom": "14px",
                                                        "textTransform": "uppercase", "letterSpacing": "0.08em"}),
            html.Div(id="tabla-operadores", style={"overflowX": "auto"}),
        ], style={**card_style(COLORS["amber"]), "marginBottom": "20px"}),

    ], style={"padding": "20px 24px"}),

    # ── MODALES SMART ─────────────────────────────────────────────────────────
    *[make_modal(k) for k in SMART.keys()],

    # ── FOOTER ────────────────────────────────────────────────────────────────
    html.Div([
        html.Span("Planta F · Dashboard Operaciones · Principios Tufte & Few"),
        html.Span(f"KPIs bajo metodología SMART · Datos: 2024–2025 · {len(DF)} registros"),
    ], style={
        "borderTop": f"1px solid {COLORS['border']}",
        "padding": "12px 24px", "display": "flex", "justifyContent": "space-between",
        "fontSize": "9px", "fontFamily": "monospace", "color": COLORS["textdim"],
    }),

    # CSS global
        # CSS global
    html.Div([
        html.Script("""
            body { background: #080b0f; color: #e8edf3; margin: 0; }
            * { box-sizing: border-box; }
            ::-webkit-scrollbar { width: 6px; height: 6px; }
            ::-webkit-scrollbar-track { background: #0e1318; }
            ::-webkit-scrollbar-thumb { background: #232e3c; border-radius: 3px; }
            .Select-control, .Select-menu-outer { background: #1c2530 !important; color: #e8edf3 !important; border-color: #232e3c !important; }
            .Select-value-label { color: #e8edf3 !important; }
            .Select-option { background: #1c2530 !important; color: #e8edf3 !important; }
            .Select-option:hover { background: #141b22 !important; }
            .DateInput_input { background: #1c2530 !important; color: #e8edf3 !important; border-color: #232e3c !important; font-size: 11px; }
            .DateInput { background: transparent !important; }
            .SingleDatePickerInput { background: #1c2530 !important; border-color: #232e3c !important; }
            .modal-content { background: #141b22 !important; border-color: #232e3c !important; }
            .modal-header { border-bottom-color: #232e3c !important; }
            .btn-close { filter: invert(1); }
            @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
        """)
    ]),

], style={"background": COLORS["bg0"], "minHeight": "100vh"})


# ── HELPER: FILTRAR DATOS ─────────────────────────────────────────────────────
def filtrar(desde, hasta, linea, turno, producto):
    df = DF.copy()
    if desde: df = df[df["fecha"] >= pd.to_datetime(desde)]
    if hasta: df = df[df["fecha"] <= pd.to_datetime(hasta)]
    if linea:    df = df[df["linea"]    == linea]
    if turno:    df = df[df["turno"]    == turno]
    if producto: df = df[df["producto"] == producto]
    return df


# ── CALLBACK PRINCIPAL ────────────────────────────────────────────────────────
@app.callback(
    Output("rec-count",        "children"),
    Output("kpi-cards",        "children"),
    Output("g-gauge",          "figure"),
    Output("g-prod",           "figure"),
    Output("g-defectos",       "figure"),
    Output("g-turnos",         "figure"),
    Output("g-margen",         "figure"),
    Output("g-paros",          "figure"),
    Output("tabla-operadores", "children"),
    Input("f-desde",   "date"),
    Input("f-hasta",   "date"),
    Input("f-linea",   "value"),
    Input("f-turno",   "value"),
    Input("f-producto","value"),
)
def actualizar(desde, hasta, linea, turno, producto):
    df = filtrar(desde, hasta, linea, turno, producto)
    n = len(df)

    if n == 0:
        empty = go.Figure().update_layout(**PLOTLY_LAYOUT)
        return [f"Registros: 0", [], empty, empty, empty, empty, empty, empty, html.Div("Sin datos")]

    # ── KPIs agregados ───────────────────────────────────────────────────────
    oee   = df["oee"].mean()
    disp  = df["disponibilidad"].mean()
    perf  = df["performance"].mean()
    cal   = df["calidad"].mean()
    fpy   = df["fpy"].mean()
    def_r = df["tasa_defectos"].mean()
    retr  = df["retrabajo_pct"].mean()
    otd   = (df["a_tiempo"] == 1).mean()
    mrg   = df["margen"].mean()
    ciclo = df["tiempo_ciclo_min"].mean()
    paros = df["paros_min"].mean()
    hext  = df["horas_extra"].mean()

    # ── KPI CARDS ────────────────────────────────────────────────────────────
    def kpi_card(kpi_id, nombre, valor_str, pct_bar, ok, accent, unit=""):
        color_ok = COLORS["green"] if ok else COLORS["red"]
        delta_txt = "▲ En objetivo" if ok else "▼ Bajo objetivo"
        return html.Div([
            html.Div([
                html.Div(nombre, style={
                    "fontSize": "10px", "fontFamily": "monospace", "color": COLORS["textdim"],
                    "textTransform": "uppercase", "letterSpacing": "0.08em",
                    "lineHeight": "1.3", "flex": "1", "paddingRight": "6px",
                }),
                html.Button("i", id=f"btn-{kpi_id}", n_clicks=0, style={
                    "width": "18px", "height": "18px", "minWidth": "18px",
                    "background": "transparent", "border": f"1px solid {COLORS['border']}",
                    "color": COLORS["text2"], "borderRadius": "50%", "cursor": "pointer",
                    "fontSize": "9px", "fontWeight": "700", "fontFamily": "monospace",
                    "display": "flex", "alignItems": "center", "justifyContent": "center",
                }),
            ], style={"display": "flex", "alignItems": "flex-start",
                      "justifyContent": "space-between", "marginBottom": "8px"}),
            html.Div([
                html.Span(valor_str, style={"fontSize": "26px", "fontWeight": "700",
                                             "fontFamily": "monospace", "color": COLORS["text"]}),
                html.Span(unit, style={"fontSize": "12px", "color": COLORS["text2"], "marginLeft": "3px"}),
            ]),
            html.Div(delta_txt, style={"fontSize": "10px", "fontFamily": "monospace",
                                        "color": color_ok, "margin": "4px 0 6px"}),
            html.Div([
                html.Div(style={
                    "height": "3px", "borderRadius": "2px", "background": accent,
                    "width": f"{max(2, min(100, pct_bar * 100)):.0f}%",
                    "transition": "width 0.6s",
                })
            ], style={"width": "100%", "height": "3px", "background": COLORS["bg3"], "borderRadius": "2px"}),
        ], style={
            "background": COLORS["bg2"], "border": f"1px solid {COLORS['border']}",
            "borderRadius": "6px", "padding": "14px 16px",
            "borderTop": f"2px solid {accent}",
        })

    cards = [
        kpi_card("oee",          "OEE Global",          fmt_pct(oee),   oee,              oee >= 0.85,   COLORS["amber"]),
        kpi_card("fpy",          "First Pass Yield",    fmt_pct(fpy),   fpy,              fpy >= 0.97,   COLORS["green"]),
        kpi_card("defectos",     "Tasa de Defectos",    fmt_pct(def_r), 1 - def_r,        def_r <= 0.03, COLORS["red"]),
        kpi_card("retrabajo",    "% Retrabajo",         fmt_pct(retr),  1 - retr * 10,    retr <= 0.015, COLORS["amber"]),
        kpi_card("disponibilidad","Disponibilidad",     fmt_pct(disp),  disp,             disp >= 0.95,  COLORS["teal"]),
        kpi_card("entrega",      "Entregas a Tiempo",   fmt_pct(otd),   otd,              otd >= 0.90,   COLORS["blue"]),
        kpi_card("margen",       "Margen Bruto",        fmt_pct(mrg),   mrg,              mrg >= 0.25,   COLORS["green"]),
        kpi_card("ciclo",        "Tiempo de Ciclo",     fmt1(ciclo),    min(1,4.5/ciclo), ciclo <= 4.5,  COLORS["amber"], "min"),
        kpi_card("paros",        "Paros Promedio",      fmt1(paros),    max(0,1-paros/30),paros <= 8,    COLORS["red"],   "min"),
        kpi_card("horas_extra",  "Horas Extra",         fmt2(hext),     max(0,1-hext/2),  hext <= 0.8,   COLORS["amber"], "h"),
    ]

    # ── GAUGE ─────────────────────────────────────────────────────────────────
    oee_color = COLORS["green"] if oee >= 0.85 else (COLORS["amber"] if oee >= 0.70 else COLORS["red"])

    fig_gauge = go.Figure()
    fig_gauge.add_trace(go.Indicator(
        mode="gauge+number",
        value=round(oee * 100, 1),
        number={"suffix": "%", "font": {"size": 32, "color": oee_color, "family": "monospace"}},
        gauge=dict(
            axis=dict(range=[0, 100], tickfont=dict(size=9, color=COLORS["textdim"]),
                      tickcolor=COLORS["textdim"], tickwidth=1),
            bar=dict(color=oee_color, thickness=0.25),
            bgcolor=COLORS["bg3"],
            borderwidth=0,
            steps=[
                dict(range=[0, 70],  color="#7f1d1d"),
                dict(range=[70, 85], color="#a06a10"),
                dict(range=[85, 100],color="#14532d"),
            ],
            threshold=dict(line=dict(color=COLORS["text"], width=2), thickness=0.75, value=85),
        ),
        domain=dict(x=[0, 1], y=[0.15, 1]),
    ))

    # Componentes OEE debajo del gauge
    fig_gauge.add_annotation(x=0.15, y=0.08, text=f"D: {fmt_pct(disp)}", showarrow=False,
                              font=dict(size=10, color=COLORS["teal"], family="monospace"),
                              xref="paper", yref="paper")
    fig_gauge.add_annotation(x=0.50, y=0.08, text=f"P: {fmt_pct(perf)}", showarrow=False,
                              font=dict(size=10, color=COLORS["amber"], family="monospace"),
                              xref="paper", yref="paper")
    fig_gauge.add_annotation(x=0.85, y=0.08, text=f"Q: {fmt_pct(cal)}", showarrow=False,
                              font=dict(size=10, color=COLORS["green"], family="monospace"),
                              xref="paper", yref="paper")

    fig_gauge.update_layout(
        **{**PLOTLY_LAYOUT, "margin": dict(l=20, r=20, t=10, b=30), "showlegend": False}
    )

    # ── PRODUCCIÓN MENSUAL ────────────────────────────────────────────────────
    pm = (df.groupby("mes")
            .agg(produccion=("unidades_producidas", "sum"),
                 oee_mean=("oee", "mean"))
            .reset_index()
            .sort_values("mes"))

    fig_prod = go.Figure()
    fig_prod.add_trace(go.Bar(
        x=pm["mes"], y=pm["produccion"], name="Unidades",
        marker_color=COLORS["teal"], opacity=0.7,
        marker_line_width=0, yaxis="y",
    ))
    fig_prod.add_trace(go.Scatter(
        x=pm["mes"], y=pm["oee_mean"] * 100, name="OEE %",
        mode="lines+markers", line=dict(color=COLORS["amber"], width=2),
        marker=dict(size=4), yaxis="y2",
    ))
    fig_prod.update_layout(**{
        **PLOTLY_LAYOUT,
        "yaxis":  dict(title="Unidades", gridcolor="#141b22", gridwidth=1, zeroline=False, showline=False, tickfont=dict(size=9)),
        "yaxis2": dict(title="OEE %", overlaying="y", side="right", range=[60, 100],
                       showgrid=False, zeroline=False, showline=False, tickfont=dict(size=9),
                       ticksuffix="%"),
        "xaxis":  dict(showgrid=False, zeroline=False, showline=False, tickfont=dict(size=9), tickangle=45),
        "barmode": "group",
    })

    # ── DEFECTOS POR LÍNEA / TURNO ────────────────────────────────────────────
    turnos_c = {"Matutino": COLORS["amber"], "Vespertino": COLORS["teal"], "Nocturno": COLORS["blue"]}
    fig_def = go.Figure()
    for t, c in turnos_c.items():
        sub = df[df["turno"] == t].groupby("linea")["tasa_defectos"].mean() * 100
        fig_def.add_trace(go.Bar(
            name=t, x=sub.index, y=sub.values,
            marker_color=c, opacity=0.75, marker_line_width=0,
        ))
    fig_def.update_layout(**{**PLOTLY_LAYOUT, "barmode": "group",
                              "yaxis": dict(gridcolor="#141b22", zeroline=False, showline=False,
                                            tickfont=dict(size=9), ticksuffix="%")})

    # ── TURNOS DONUT ──────────────────────────────────────────────────────────
    tc = df["turno"].value_counts()
    fig_tur = go.Figure(go.Pie(
        labels=tc.index, values=tc.values,
        hole=0.65,
        marker=dict(colors=[COLORS["amber"], COLORS["teal"], COLORS["blue"]],
                    line=dict(color=COLORS["bg2"], width=2)),
        textfont=dict(size=9, family="monospace"),
        insidetextorientation="radial",
    ))
    fig_tur.update_layout(**{**PLOTLY_LAYOUT, "showlegend": True,
                              "legend": dict(orientation="v", x=0.75, y=0.5,
                                             font=dict(size=9, color=COLORS["text2"]))})

    # ── MARGEN + OTD ──────────────────────────────────────────────────────────
    mm = (df.groupby("mes")
            .agg(margen_m=("margen", "mean"),
                 otd_m=("a_tiempo", "mean"))
            .reset_index()
            .sort_values("mes"))

    fig_mrg = go.Figure()
    fig_mrg.add_trace(go.Scatter(
        x=mm["mes"], y=mm["margen_m"] * 100, name="Margen %",
        mode="lines+markers", fill="tozeroy",
        line=dict(color=COLORS["green"], width=2),
        fillcolor="rgba(74,222,128,0.06)", marker=dict(size=4),
    ))
    fig_mrg.add_trace(go.Scatter(
        x=mm["mes"], y=mm["otd_m"] * 100, name="OTD %",
        mode="lines+markers", fill="tozeroy",
        line=dict(color=COLORS["blue"], width=2),
        fillcolor="rgba(96,165,250,0.06)", marker=dict(size=4),
    ))
    fig_mrg.update_layout(**{**PLOTLY_LAYOUT,
                              "yaxis": dict(gridcolor="#141b22", zeroline=False, showline=False,
                                            tickfont=dict(size=9), ticksuffix="%")})

    # ── PAROS + HORAS EXTRA ───────────────────────────────────────────────────
    pm2 = (df.groupby("mes")
             .agg(paros_m=("paros_min", "mean"),
                  hext_m=("horas_extra", "mean"))
             .reset_index()
             .sort_values("mes"))

    fig_par = go.Figure()
    fig_par.add_trace(go.Bar(
        x=pm2["mes"], y=pm2["paros_m"], name="Paros (min)",
        marker_color=COLORS["red"], opacity=0.7, marker_line_width=0, yaxis="y",
    ))
    fig_par.add_trace(go.Scatter(
        x=pm2["mes"], y=pm2["hext_m"], name="Hrs Extra",
        mode="lines+markers", line=dict(color=COLORS["amber"], width=1.5),
        marker=dict(size=3), yaxis="y2",
    ))
    fig_par.update_layout(**{
        **PLOTLY_LAYOUT,
        "yaxis":  dict(gridcolor="#141b22", zeroline=False, showline=False, tickfont=dict(size=9)),
        "yaxis2": dict(overlaying="y", side="right", showgrid=False,
                       zeroline=False, showline=False, tickfont=dict(size=9)),
    })

    # ── TABLA OPERADORES ──────────────────────────────────────────────────────
    by_op = (df.groupby("operador")
               .agg(n=("oee", "count"),
                    prod=("unidades_producidas", "sum"),
                    oee_m=("oee", "mean"),
                    def_m=("tasa_defectos", "mean"),
                    retr_m=("retrabajo_pct", "mean"),
                    hext_m=("horas_extra", "mean"))
               .reset_index()
               .sort_values("oee_m", ascending=False))

    medals = ["🥇", "🥈", "🥉"]

    def pill(txt, color, bg):
        return html.Span(txt, style={
            "padding": "2px 8px", "borderRadius": "10px", "fontSize": "9px",
            "fontFamily": "monospace", "fontWeight": "600",
            "color": color, "background": bg,
            "border": f"1px solid {color}55",
        })

    header_style = {"padding": "8px 16px", "fontSize": "9px", "fontFamily": "monospace",
                    "color": COLORS["textdim"], "textTransform": "uppercase",
                    "letterSpacing": "0.1em", "borderBottom": f"1px solid {COLORS['border']}",
                    "textAlign": "left", "whiteSpace": "nowrap", "background": COLORS["bg2"]}
    cell_style = {"padding": "8px 16px", "fontSize": "12px", "fontFamily": "monospace",
                  "color": COLORS["text2"], "borderBottom": f"1px solid {COLORS['border']}"}

    rows = []
    for i, r in by_op.iterrows():
        rank = medals[list(by_op.index).index(i)] if list(by_op.index).index(i) < 3 else str(list(by_op.index).index(i) + 1)
        oee_ok = r["oee_m"] >= 0.85
        oee_pill = pill(fmt_pct(r["oee_m"]),
                        COLORS["green"] if oee_ok else (COLORS["amber"] if r["oee_m"] >= 0.75 else COLORS["red"]),
                        "#14532d" if oee_ok else ("#a06a1020" if r["oee_m"] >= 0.75 else "#7f1d1d20"))
        status_pill = pill(
            "Óptimo" if oee_ok else ("Normal" if r["oee_m"] >= 0.75 else "Revisar"),
            COLORS["green"] if oee_ok else (COLORS["amber"] if r["oee_m"] >= 0.75 else COLORS["red"]),
            "#14532d20" if oee_ok else ("#a06a1020" if r["oee_m"] >= 0.75 else "#7f1d1d20"),
        )
        rows.append(html.Tr([
            html.Td(rank,                               style=cell_style),
            html.Td(r["operador"],                      style={**cell_style, "color": COLORS["text"], "fontWeight": "600"}),
            html.Td(str(int(r["n"])),                   style=cell_style),
            html.Td(f"{int(r['prod']):,}",              style=cell_style),
            html.Td(oee_pill),
            html.Td(fmt_pct(r["def_m"]),                style={**cell_style, "color": COLORS["red"] if r["def_m"] > 0.03 else COLORS["text2"]}),
            html.Td(fmt_pct(r["retr_m"]),               style=cell_style),
            html.Td(f"{r['hext_m']:.2f}",               style={**cell_style, "color": COLORS["amber"] if r["hext_m"] > 0.8 else COLORS["text2"]}),
            html.Td(status_pill),
        ]))

    tabla = html.Table([
        html.Thead(html.Tr([
            html.Th("#",              style=header_style),
            html.Th("Operador",       style=header_style),
            html.Th("Registros",      style=header_style),
            html.Th("Unidades",       style=header_style),
            html.Th("OEE Prom.",      style=header_style),
            html.Th("Defectos %",     style=header_style),
            html.Th("Retrabajo %",    style=header_style),
            html.Th("Hrs Extra",      style=header_style),
            html.Th("Estatus",        style=header_style),
        ])),
        html.Tbody(rows),
    ], style={"width": "100%", "borderCollapse": "collapse"})

    rec_label = [f"Registros: ", html.Span(str(n), style={"color": COLORS["amber"]})]

    return rec_label, cards, fig_gauge, fig_prod, fig_def, fig_tur, fig_mrg, fig_par, tabla


# ── CALLBACKS MODALES ─────────────────────────────────────────────────────────
for kpi_id in SMART.keys():
    @app.callback(
        Output(f"modal-{kpi_id}", "is_open"),
        Input(f"btn-{kpi_id}", "n_clicks"),
        State(f"modal-{kpi_id}", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_modal(n, is_open, _id=kpi_id):
        return not is_open if n else is_open


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  🏭  PLANTA F — Dashboard de Operaciones")
    print("="*55)
    print(f"  Datos cargados: {len(DF)} registros")
    print(f"  Rango: {DF['fecha'].min().date()} → {DF['fecha'].max().date()}")
    print(f"  Líneas: {sorted(DF['linea'].unique())}")
    print(f"  Turnos: {sorted(DF['turno'].unique())}")
    print("="*55)
    print("  ▶  Abre tu navegador en: http://127.0.0.1:8050")
    print("="*55 + "\n")
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, host="0.0.0.0", port=port)