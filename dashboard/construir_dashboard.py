"""Etapa 4 - Dashboard.

Genera docs/dashboard.html: una página interactiva (Plotly) que se abre con doble clic
en cualquier navegador, sin servidor. Por defecto incluye la librería Plotly dentro del
propio archivo (~4 MB), así que funciona sin conexión a internet.

Interactividad: pasar el cursor muestra los valores; se puede acercar con el mouse y
activar o apagar series haciendo clic en la leyenda.

Uso:
    python dashboard/construir_dashboard.py
    python dashboard/construir_dashboard.py --cdn      # archivo liviano, requiere internet al abrirlo
"""
import argparse
import html
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from dashboard import datos  # noqa: E402
from dashboard.datos import ErrorDashboard  # noqa: E402

SALIDA = config.DOCS / "dashboard.html"
COLORES = {"Terciario": "#2f5597", "Secundario": "#c0504d", "Primario": "#548235", config.SIN_CLASIFICAR: "#7f7f7f"}
AZUL = "#2f5597"


# ---------------------------------------------------------------------------
# Formato de números en español (punto de miles, coma decimal)
# ---------------------------------------------------------------------------
def _es(x: float, decimales: int = 0) -> str:
    texto = f"{x:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _pesos(x: float) -> str:
    if x >= 1_000_000:
        return f"${_es(x / 1_000_000, 1)} M"
    return f"${_es(x)}"


# ---------------------------------------------------------------------------
# Figuras (cada función recibe los agregados y devuelve una figura de Plotly)
# ---------------------------------------------------------------------------
def _base(go, titulo: str, alto: int = 380):
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=titulo, x=0.02),
        template="plotly_white", height=alto,
        margin=dict(l=10, r=10, t=55, b=10),
        font=dict(family="Segoe UI, Arial, sans-serif", size=12),
        showlegend=False,
    )
    return fig


def fig_macro_sector(go, d):
    t = d["macro_sector"]
    fig = _base(go, "Empresas por macro sector")
    fig.add_trace(go.Bar(
        x=t["macro_sector"].tolist(), y=t["empresas"].tolist(),
        marker=dict(color=[COLORES.get(m, "#7f7f7f") for m in t["macro_sector"]]),
        text=[f"{_es(p, 1)} %" for p in t["pct"]], textposition="outside",
        hovertext=[f"{m}: {_es(n)} empresas ({_es(p, 1)} %)" for m, n, p in zip(t["macro_sector"], t["empresas"], t["pct"])],
        hoverinfo="text",
    ))
    fig.update_yaxes(title_text="Empresas")
    return fig


def fig_municipio(go, d):
    t = d["municipio"]
    fig = _base(go, "Top 10 municipios por número de empresas")
    fig.add_trace(go.Bar(
        x=t["empresas"].tolist(), y=t["mun_nombre"].tolist(), orientation="h",
        marker=dict(color=AZUL),
        text=[f"{_es(p, 1)} %" for p in t["pct"]], textposition="outside",
        hovertext=[f"{m}: {_es(n)} empresas ({_es(p, 1)} %)" for m, n, p in zip(t["mun_nombre"], t["empresas"], t["pct"])],
        hoverinfo="text",
    ))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="Empresas")
    return fig


def fig_seccion(go, d):
    t = d["seccion"]
    fig = _base(go, "Empresas por sección CIIU (clic en la leyenda para filtrar por macro sector)")
    fig.update_layout(showlegend=True, barmode="overlay", legend=dict(orientation="h", y=1.02, x=0.0))
    for macro in [m for m in datos.ORDEN_MACRO if m in set(t["macro_sector"])]:
        s = t[t["macro_sector"] == macro]
        nombres = [textwrap.shorten(n.capitalize(), width=70, placeholder="...") for n in s["seccion_nombre"]]
        fig.add_trace(go.Bar(
            name=macro, x=s["seccion_letra"].tolist(), y=s["empresas"].tolist(),
            marker=dict(color=COLORES.get(macro, "#7f7f7f")),
            hovertext=[f"Sección {l}: {n}<br>{_es(e)} empresas ({_es(p, 1)} %)"
                       for l, n, e, p in zip(s["seccion_letra"], nombres, s["empresas"], s["pct"])],
            hoverinfo="text",
        ))
    fig.update_xaxes(title_text="Sección CIIU", categoryorder="array", categoryarray=t["seccion_letra"].tolist())
    fig.update_yaxes(title_text="Empresas")
    return fig


def fig_matriculas(go, d):
    t, fecha = d["matriculas"], d["indicadores"]["fecha_corte"]
    completos, parciales = t[~t["anio_parcial"]], t[t["anio_parcial"]]
    fig = _base(go, "Nuevas matrículas por año")
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.02, x=0.0))
    fig.add_trace(go.Scatter(
        x=completos["anio_matricula"].tolist(), y=completos["empresas"].tolist(),
        mode="lines+markers", name="Año completo", line=dict(color=AZUL, width=2), marker=dict(size=5),
        hovertext=[f"{a}: {_es(n)} matrículas" for a, n in zip(completos["anio_matricula"], completos["empresas"])],
        hoverinfo="text",
    ))
    if not parciales.empty:
        fig.add_trace(go.Scatter(
            x=parciales["anio_matricula"].tolist(), y=parciales["empresas"].tolist(),
            mode="markers", name=f"Año parcial (corte {fecha})",
            marker=dict(size=11, color="#c0504d", symbol="diamond"),
            hovertext=[f"{a}: {_es(n)} matrículas (año incompleto, no es una caída real)"
                       for a, n in zip(parciales["anio_matricula"], parciales["empresas"])],
            hoverinfo="text",
        ))
    fig.update_xaxes(title_text="Año de matrícula")
    fig.update_yaxes(title_text="Empresas")
    return fig


def fig_valor(go, d):
    t = d["valor"]
    fig = _base(go, "Mediana del valor del establecimiento por macro sector")
    fig.add_trace(go.Bar(
        x=t["macro_sector"].tolist(), y=t["mediana"].tolist(),
        marker=dict(color=[COLORES.get(m, "#7f7f7f") for m in t["macro_sector"]]),
        text=[_pesos(v) for v in t["mediana"]], textposition="outside",
        hovertext=[f"{m}: mediana {_pesos(v)} COP (n = {_es(n)} empresas con valor reportado)"
                   for m, v, n in zip(t["macro_sector"], t["mediana"], t["n"])],
        hoverinfo="text",
    ))
    fig.update_yaxes(title_text="Pesos colombianos (COP)")
    return fig


def fig_barrios(go, d):
    t = d["barrios"]
    fig = _base(go, "Top 15 barrios de Pasto por número de empresas")
    fig.add_trace(go.Bar(
        x=t["empresas"].tolist(), y=t["barrio_nombre"].tolist(), orientation="h",
        marker=dict(color="#548235"),
        text=[f"{_es(p, 1)} %" for p in t["pct"]], textposition="outside",
        hovertext=[f"{b}: {_es(n)} empresas ({_es(p, 1)} % de las que informan barrio)"
                   for b, n, p in zip(t["barrio_nombre"], t["empresas"], t["pct"])],
        hoverinfo="text",
    ))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="Empresas")
    return fig


# ---------------------------------------------------------------------------
# Página HTML
# ---------------------------------------------------------------------------
CSS = """
:root { --fondo:#f4f6fa; --tarjeta:#ffffff; --texto:#1f2937; --suave:#6b7280; --azul:#2f5597; --borde:#e5e7eb; }
@media (prefers-color-scheme: dark) {
  :root { --fondo:#111827; --tarjeta:#1f2937; --texto:#f3f4f6; --suave:#9ca3af; --azul:#8faadc; --borde:#374151; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--fondo); color:var(--texto); font-family:"Segoe UI", Arial, sans-serif; }
header, main, footer { max-width:1280px; margin:0 auto; padding:18px 20px; }
h1 { margin:0 0 4px; font-size:1.5rem; color:var(--azul); }
.sub { color:var(--suave); font-size:.9rem; margin:0; }
.aviso { background:#fff4ce; color:#7a5b00; border-left:4px solid #e0a800; padding:10px 14px; border-radius:6px; margin-top:12px; font-size:.9rem; }
.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin:14px 0 6px; }
.kpi { background:var(--tarjeta); border:1px solid var(--borde); border-radius:10px; padding:12px 14px; }
.kpi .v { font-size:1.55rem; font-weight:700; color:var(--azul); }
.kpi .t { font-size:.8rem; color:var(--suave); margin-top:2px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(480px,1fr)); gap:14px; }
.card { background:var(--tarjeta); border:1px solid var(--borde); border-radius:10px; padding:6px; min-width:0; }
.card.ancho { grid-column:1 / -1; }
footer { color:var(--suave); font-size:.82rem; line-height:1.5; }
footer li { margin-bottom:3px; }
@media (max-width:560px) { .grid { grid-template-columns:1fr; } }
"""


def _tarjeta(valor: str, titulo: str) -> str:
    return f'<div class="kpi"><div class="v">{html.escape(valor)}</div><div class="t">{html.escape(titulo)}</div></div>'


def construir_pagina(d: dict, figuras: list, cdn: bool) -> str:
    """figuras: lista de (figura, ancho_completo)."""
    k = d["indicadores"]
    config_plotly = {"displaylogo": False, "responsive": True}
    bloques = []
    for i, (fig, ancho) in enumerate(figuras):
        js = ("cdn" if cdn else True) if i == 0 else False       # la librería se incluye una sola vez
        div = fig.to_html(full_html=False, include_plotlyjs=js, config=config_plotly)
        bloques.append(f'<div class="card{" ancho" if ancho else ""}">{div}</div>')

    aviso = ""
    if k["es_muestra"]:
        aviso = (f'<div class="aviso"><b>Atención:</b> este tablero se generó con la <b>muestra anonimizada</b> '
                 f'({_es(k["empresas"])} registros), no con el archivo completo. Las cifras son una muestra aleatoria.</div>')

    tarjetas = "".join([
        _tarjeta(_es(k["empresas"]), "Empresas registradas"),
        _tarjeta(_es(k["municipios"]), "Municipios"),
        _tarjeta(f'{_es(k["pct_pasto"], 1)} %', "Empresas en Pasto"),
        _tarjeta(f'{_es(k["pct_terciario"], 1)} %', "Sector terciario"),
        _tarjeta(_pesos(k["mediana_valor"]), "Mediana del valor del establecimiento"),
        _tarjeta(f'{_es(k["mediana_antiguedad"], 1)} años', "Antigüedad mediana"),
    ])

    notas = [
        f'Fuente: registro mercantil de la Cámara de Comercio de Pasto ({html.escape(k["fuente"])}, fecha de corte {k["fecha_corte"]}) '
        "y clasificación CIIU Rev. 4 A.C. del DANE (versión 2020). Es una fotografía, no una serie continua.",
        "El último año de matrícula está incompleto por la fecha de corte: se marca como parcial y no debe leerse como una caída.",
        f'El valor del establecimiento se resume con la <b>mediana</b> y solo con valores reportados '
        f'(se excluye el {_es(k["pct_valor_no_reportado"], 1)} % en cero o sin dato): el promedio está distorsionado por unas pocas entidades muy grandes.',
        "El barrio solo viene informado para Pasto; en los otros municipios el dato no existe en la fuente.",
        "El código de estado de la matrícula (EST_DATOS) no se grafica: la fuente no incluye un diccionario oficial que permita interpretarlo.",
    ]
    lista = "".join(f"<li>{n}</li>" for n in notas)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tejido empresarial de Nariño - Registro mercantil, Cámara de Comercio de Pasto</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>Tejido empresarial de Nariño</h1>
  <p class="sub">Registro mercantil de la Cámara de Comercio de Pasto, enriquecido con la clasificación CIIU del DANE</p>
  {aviso}
  <div class="kpis">{tarjetas}</div>
</header>
<main>
  <div class="grid">
    {"".join(bloques)}
  </div>
</main>
<footer>
  <b>Notas de lectura</b>
  <ul>{lista}</ul>
</footer>
</body>
</html>
"""


def construir(salida: Path = SALIDA, cdn: bool = False) -> Path:
    try:
        import plotly.graph_objects as go
    except ImportError as e:
        raise ErrorDashboard("Falta la librería plotly. Instálela con: pip install -r requirements.txt") from e

    d = datos.todos()
    figuras = [
        (fig_macro_sector(go, d), False),
        (fig_municipio(go, d), False),
        (fig_seccion(go, d), True),
        (fig_matriculas(go, d), False),
        (fig_valor(go, d), False),
        (fig_barrios(go, d), False),
    ]
    pagina = construir_pagina(d, figuras, cdn)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(pagina, encoding="utf-8")
    return salida


def ejecutar(cdn: bool = False) -> Path:
    ruta = construir(cdn=cdn)
    print(f"[Dashboard] Generado: {ruta} ({ruta.stat().st_size / 1e6:.1f} MB). Ábralo con doble clic en el navegador.")
    return ruta


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el dashboard interactivo (Plotly)")
    parser.add_argument("--cdn", action="store_true", help="No incluir Plotly en el archivo (requiere internet al abrirlo)")
    args = parser.parse_args()
    try:
        ejecutar(cdn=args.cdn)
    except ErrorDashboard as e:
        print(f"[Dashboard] ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
