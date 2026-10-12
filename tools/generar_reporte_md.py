"""Convierte data/processed/reporte_calidad.csv en una tabla Markdown agrupada por tema.

Así la sección 10 del README sale del reporte que genera el propio pipeline y no se
escribe a mano. Las verificaciones nuevas que no estén en ningún grupo aparecen en
"Otras verificaciones" (nunca se omiten).

Uso (después de ejecutar el pipeline):
    python tools/generar_reporte_md.py
    python tools/generar_reporte_md.py --salida docs/reporte_calidad_archivo_completo.md
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

# (título del grupo, fragmentos que identifican sus verificaciones) - el orden importa
GRUPOS = [
    ("Volumen e integridad", ["Número de registros", "duplicados", "Número de columnas", "Valores nulos en columnas clave"]),
    ("Privacidad", ["datos personales", "Teléfonos o correos"]),
    ("Fechas", ["Fechas de matrícula", "Antigüedad negativa", "año de corte"]),
    ("Municipio, barrio y clasificación CIIU", ["Municipio nulo", "sin CIIU", "Códigos CIIU sin coincidencia",
                                                 "perdidos en el join", "Letra CIIU", "Barrios", "Municipios con barrio"]),
    ("Valor del establecimiento", ["en cero", "negativos", "menores a $1.000", "Valor mínimo", "Valor máximo", "outlier"]),
    ("Texto", ["espacios dobles"]),
    ("Carga a la base (Load)", ["[Load]"]),
]


def _numero(valor: str) -> str:
    """Formato español: miles con punto y decimales con coma. Lo que no es número se deja igual."""
    if valor is None or valor in ("-", ""):
        return valor or "-"
    try:
        x = float(valor)
    except ValueError:
        return valor
    decimales = 0 if (x == int(x) or abs(x) >= 1000) else 1     # pesos grandes sin decimales
    texto = f"{x:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _grupo(verificacion: str) -> str:
    for titulo, claves in GRUPOS:
        if any(c in verificacion for c in claves):
            return titulo
    return "Otras verificaciones"


def generar(entrada: Path) -> str:
    if not entrada.exists():
        raise SystemExit(f"No existe {entrada.name}. Ejecute primero: python pipeline.py")
    rep = pd.read_csv(entrada, dtype=str, keep_default_na=False)
    fuente = rep.iloc[0]
    meta = json.loads(config.EXTRACCION_META.read_text(encoding="utf-8")) if config.EXTRACCION_META.exists() else {}

    rep = rep.iloc[1:].copy()                       # la fila 0 ("Fuente usada") va en el encabezado
    rep["grupo"] = rep["verificacion"].map(_grupo)

    lineas = [f"# Reporte de calidad de datos", "",
              f"- **Fuente:** `{fuente['antes']}` ({fuente['nota']}, {_numero(str(meta.get('filas_registro', '')))} registros)",
              f"- **Generado:** {meta.get('fecha_extraccion', 'desconocida')}", ""]
    ordenados = [t for t, _ in GRUPOS] + ["Otras verificaciones"]
    for titulo in ordenados:
        sub = rep[rep["grupo"] == titulo]
        if sub.empty:
            continue
        lineas += [f"## {titulo}", "", "| Verificación | Antes | Después | Nota |", "|---|---|---|---|"]
        for _, f in sub.iterrows():
            nombre = re.sub(r"^\[Load\] ", "", f["verificacion"])
            lineas.append(f"| {nombre} | {_numero(f['antes'])} | {_numero(f['despues'])} | {f['nota'].replace('|', '/')} |")
        lineas.append("")
    return "\n".join(lineas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reporte de calidad en Markdown")
    parser.add_argument("--entrada", type=Path, default=config.REPORTE_CALIDAD)
    parser.add_argument("--salida", type=Path, default=config.DOCS / "reporte_calidad.md")
    args = parser.parse_args()
    texto = generar(args.entrada)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(texto, encoding="utf-8")
    print(f"Reporte generado: {args.salida} ({sum(1 for l in texto.splitlines() if l.startswith('| ') and not l.startswith('| Verif'))} verificaciones)")


if __name__ == "__main__":
    main()
