"""Genera una figura estática con los resultados del pipeline (docs/resultados.png).

Usa los MISMOS agregados que el dashboard interactivo (dashboard/datos.py), de modo que
la imagen y el tablero cuentan la misma historia. Sirve como evidencia en el README y
como respaldo si no se puede abrir el dashboard.

Requiere matplotlib (solo para esta utilidad; el pipeline no lo necesita):
    pip install matplotlib

Uso (después de ejecutar el pipeline):
    python tools/generar_figuras.py
    python tools/generar_figuras.py --salida docs/resultados_archivo_completo.png
"""
import argparse
import sys
from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from dashboard import datos  # noqa: E402

COLORES = {"Terciario": "#2f5597", "Secundario": "#c0504d", "Primario": "#548235", config.SIN_CLASIFICAR: "#7f7f7f"}


def _es(x, dec=0):
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pesos(x):
    return f"${_es(x / 1e6, 1)} M" if x >= 1e6 else f"${_es(x)}"


def _limpiar(ax):
    ax.spines[["top", "right"]].set_visible(False)


def _barras_h(ax, t, col_nombre, color, titulo):
    ax.barh(t[col_nombre][::-1], t["empresas"][::-1], color=color)
    for i, (n, p) in enumerate(zip(t["empresas"][::-1], t["pct"][::-1])):
        ax.text(n, i, f"  {_es(p, 1)} %", va="center", fontsize=7.5)
    ax.set_title(titulo, fontsize=10, loc="left", fontweight="bold")
    ax.set_xlabel("Empresas", fontsize=8.5)
    ax.tick_params(labelsize=8)
    ax.margins(x=0.16)
    _limpiar(ax)


def dibujar(d: dict) -> plt.Figure:
    k = d["indicadores"]
    fig, axes = plt.subplots(2, 3, figsize=(17, 9.2))
    (a1, a2, a3), (a4, a5, a6) = axes

    # 1. Macro sector
    t = d["macro_sector"]
    a1.bar(t["macro_sector"], t["empresas"], color=[COLORES.get(m, "#7f7f7f") for m in t["macro_sector"]])
    for i, (n, p) in enumerate(zip(t["empresas"], t["pct"])):
        a1.text(i, n, f"{_es(p, 1)} %", ha="center", va="bottom", fontsize=8)
    a1.set_title("Empresas por macro sector", fontsize=10, loc="left", fontweight="bold")
    a1.set_ylabel("Empresas", fontsize=8.5)
    a1.tick_params(labelsize=8)
    a1.margins(y=0.12)
    _limpiar(a1)

    # 2. Municipios
    _barras_h(a2, d["municipio"], "mun_nombre", COLORES["Terciario"], "Top 10 municipios")

    # 3. Secciones CIIU coloreadas por macro sector
    t = d["seccion"]
    a3.bar(t["seccion_letra"], t["empresas"], color=[COLORES.get(m, "#7f7f7f") for m in t["macro_sector"]])
    a3.set_title("Empresas por sección CIIU", fontsize=10, loc="left", fontweight="bold")
    a3.set_xlabel("Sección CIIU", fontsize=8.5)
    a3.set_ylabel("Empresas", fontsize=8.5)
    a3.tick_params(labelsize=8)
    handles = [plt.Rectangle((0, 0), 1, 1, color=COLORES[m]) for m in ("Terciario", "Secundario", "Primario")]
    a3.legend(handles, ["Terciario", "Secundario", "Primario"], fontsize=8, frameon=False)
    _limpiar(a3)

    # 4. Evolución de matrículas, con el año parcial marcado
    t = d["matriculas"]
    completos, parciales = t[~t["anio_parcial"]], t[t["anio_parcial"]]
    a4.plot(completos["anio_matricula"], completos["empresas"], marker="o", ms=3.5, color=COLORES["Terciario"], label="Año completo")
    if not parciales.empty:
        a4.scatter(parciales["anio_matricula"], parciales["empresas"], marker="D", s=55, color="#c0504d",
                   zorder=3, label=f"Año parcial (corte {k['fecha_corte']})")
    a4.set_title("Nuevas matrículas por año", fontsize=10, loc="left", fontweight="bold")
    a4.set_xlabel("Año de matrícula", fontsize=8.5)
    a4.set_ylabel("Empresas", fontsize=8.5)
    a4.tick_params(labelsize=8)
    a4.legend(fontsize=8, frameon=False, loc="upper left")
    _limpiar(a4)

    # 5. Mediana del valor
    t = d["valor"]
    a5.bar(t["macro_sector"], t["mediana"], color=[COLORES.get(m, "#7f7f7f") for m in t["macro_sector"]])
    for i, v in enumerate(t["mediana"]):
        a5.text(i, v, _pesos(v), ha="center", va="bottom", fontsize=8.5)
    a5.set_title("Mediana del valor del establecimiento", fontsize=10, loc="left", fontweight="bold")
    a5.set_ylabel("Pesos colombianos (COP)", fontsize=8.5)
    a5.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _pesos(v) if v else "$0"))
    a5.tick_params(labelsize=8)
    a5.margins(y=0.15)
    _limpiar(a5)

    # 6. Barrios de Pasto
    _barras_h(a6, d["barrios"], "barrio_nombre", "#548235", "Top 15 barrios (solo Pasto trae barrio)")

    origen = "MUESTRA anonimizada" if k["es_muestra"] else "archivo completo"
    fig.suptitle(f"Tejido empresarial de Nariño - {_es(k['empresas'])} empresas ({origen}), corte {k['fecha_corte']}",
                 fontsize=13, fontweight="bold", x=0.01, ha="left")
    fig.text(0.01, 0.005, "Medianas calculadas solo con valores reportados. El año parcial no es una caída real. "
             "Barrio informado únicamente en Pasto.", fontsize=8.5, color="#555555")
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description="Figura estática de resultados")
    parser.add_argument("--salida", type=Path, default=config.DOCS / "resultados.png")
    args = parser.parse_args()
    try:
        fig = dibujar(datos.todos())
    except datos.ErrorDashboard as e:
        raise SystemExit(f"ERROR: {e}")
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.salida, dpi=110, facecolor="white")
    print(f"Figura generada: {args.salida}")


if __name__ == "__main__":
    main()
