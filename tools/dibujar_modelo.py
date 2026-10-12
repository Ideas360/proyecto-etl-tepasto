"""Dibuja docs/modelo_datos.png (modelo estrella) leyendo la estructura REAL de la base.

Requiere matplotlib (solo para regenerar la imagen; el pipeline no lo necesita):
    pip install matplotlib

Uso (después de ejecutar el pipeline):
    python tools/dibujar_modelo.py
"""
import sqlite3
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

SALIDA = config.DOCS / "modelo_datos.png"
ALTO_FILA = 0.27
AZUL, AZUL_CLARO, GRIS = "#2f5597", "#dce6f5", "#666666"

# tabla -> (x, y_superior, ancho, color del encabezado)
POSICIONES = {
    "dim_municipio": (0.4, 6.0, 3.3, "#548235"),
    "dim_tiempo": (0.4, 3.0, 3.3, "#548235"),
    "fact_empresa": (4.9, 6.4, 4.6, AZUL),
    "dim_sector": (10.7, 5.5, 4.1, "#548235"),
}
TIPOS = {"TEXT": "texto", "INTEGER": "entero", "REAL": "decimal"}


def leer_estructura() -> dict:
    if not config.BASE_DATOS.exists():
        raise SystemExit(f"No existe {config.BASE_DATOS.name}. Ejecute primero: python pipeline.py")
    con = sqlite3.connect(config.BASE_DATOS)
    est = {}
    for tabla in POSICIONES:
        fks = {f[3]: (f[2], f[4]) for f in con.execute(f"PRAGMA foreign_key_list({tabla})")}
        est[tabla] = [{"nombre": c[1], "tipo": TIPOS.get(c[2], c[2].lower()), "pk": bool(c[5]), "fk": fks.get(c[1])}
                      for c in con.execute(f"PRAGMA table_info({tabla})")]
    con.close()
    return est


def y_fila(tabla: str, indice: int, estructura: dict) -> float:
    _, y_sup, _, _ = POSICIONES[tabla]
    return y_sup - ALTO_FILA * (indice + 1.5)   # centro de la fila (1 fila de encabezado)


def dibujar_tabla(ax, tabla: str, columnas: list) -> None:
    x, y_sup, ancho, color = POSICIONES[tabla]
    alto = ALTO_FILA * (len(columnas) + 1)
    ax.add_patch(Rectangle((x, y_sup - alto), ancho, alto, fc="white", ec=color, lw=1.6, zorder=3))
    ax.add_patch(Rectangle((x, y_sup - ALTO_FILA), ancho, ALTO_FILA, fc=color, ec=color, zorder=4))
    ax.text(x + ancho / 2, y_sup - ALTO_FILA / 2, tabla, ha="center", va="center", color="white",
            fontsize=10, fontweight="bold", zorder=5)
    for i, col in enumerate(columnas):
        y = y_sup - ALTO_FILA * (i + 1.5)
        if col["pk"] or col["fk"]:
            ax.add_patch(Rectangle((x, y - ALTO_FILA / 2), ancho, ALTO_FILA, fc=AZUL_CLARO, ec="none", zorder=3.5))
        marca = "PK" if col["pk"] else ("FK" if col["fk"] else "")
        ax.text(x + 0.08, y, marca, ha="left", va="center", fontsize=7.5, fontweight="bold", color=color, zorder=5)
        ax.text(x + 0.50, y, col["nombre"], ha="left", va="center", fontsize=8.5, family="monospace", zorder=5)
        ax.text(x + ancho - 0.08, y, col["tipo"], ha="right", va="center", fontsize=7.5, color=GRIS, zorder=5)


def dibujar_relaciones(ax, estructura: dict) -> None:
    xf, _, anchof, _ = POSICIONES["fact_empresa"]
    for i, col in enumerate(estructura["fact_empresa"]):
        if not col["fk"]:
            continue
        tabla_dim, col_dim = col["fk"]
        xd, _, ancho_d, _ = POSICIONES[tabla_dim]
        j = [c["nombre"] for c in estructura[tabla_dim]].index(col_dim)
        y1, y2 = y_fila("fact_empresa", i, estructura), y_fila(tabla_dim, j, estructura)
        if xd < xf:                                    # dimensión a la izquierda
            x1, x2, d = xf, xd + ancho_d, 1
        else:                                          # dimensión a la derecha
            x1, x2, d = xf + anchof, xd, -1
        ax.plot([x1, x2], [y1, y2], color=AZUL, lw=1.4, zorder=2)
        ax.text(x1 - 0.17 * d, y1 + 0.13, "N", ha="center", fontsize=8.5, fontweight="bold", color=AZUL)
        ax.text(x2 + 0.17 * d, y2 + 0.13, "1", ha="center", fontsize=8.5, fontweight="bold", color=AZUL)


def main() -> None:
    estructura = leer_estructura()
    fig, ax = plt.subplots(figsize=(15.2, 7.9))
    ax.set_xlim(0, 15.2)
    ax.set_ylim(0.9, 8.0)
    ax.axis("off")
    ax.text(7.6, 7.65, "Modelo estrella - Registro mercantil, Cámara de Comercio de Pasto", ha="center",
            fontsize=13, fontweight="bold")
    ax.text(7.6, 7.3, "Una fila de hechos por empresa. PK = clave primaria, FK = clave foránea. N empresas : 1 dimensión.",
            ha="center", fontsize=9, color=GRIS)
    dibujar_relaciones(ax, estructura)
    for tabla, columnas in estructura.items():
        dibujar_tabla(ax, tabla, columnas)
    config.DOCS.mkdir(parents=True, exist_ok=True)
    fig.savefig(SALIDA, dpi=140, bbox_inches="tight", facecolor="white")
    print(f"Diagrama generado: {SALIDA}")


if __name__ == "__main__":
    main()
