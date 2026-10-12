"""Etapa 1 - Extract.

Lee el registro mercantil (archivo completo o muestra anonimizada) y el catálogo
CIIU del DANE, valida que tengan el esquema esperado y guarda una copia de cada
uno en CSV, con TODOS los campos como texto.

Por qué todo como texto: al leer el Excel con tipos automáticos, pandas convierte
los códigos CIIU en números y pierde los ceros iniciales (0111 -> 111), lo que
rompe el cruce con el catálogo. Extract no interpreta ni corrige nada; eso es
trabajo de Transform.

Uso:
    python extract/extraer.py
    python extract/extraer.py --fuente RUTA/AL/ARCHIVO.xlsx
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Permite ejecutar el script directamente (python extract/extraer.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


class ErrorExtraccion(Exception):
    """Error esperable de extracción (archivo ausente o con esquema distinto)."""


def elegir_fuente(ruta: Path | None = None) -> Path:
    """Devuelve el Excel del registro mercantil a usar.

    Prioridad: ruta indicada por el usuario > archivo completo > muestra anonimizada.
    """
    if ruta is not None:
        if not ruta.exists():
            raise ErrorExtraccion(f"No existe el archivo indicado con --fuente: {ruta}")
        return ruta
    if config.FUENTE_COMPLETA.exists():
        return config.FUENTE_COMPLETA
    if config.FUENTE_MUESTRA.exists():
        return config.FUENTE_MUESTRA
    raise ErrorExtraccion(
        "No se encontró ninguna fuente. Coloque el archivo completo en "
        f"{config.FUENTE_COMPLETA} o restaure {config.FUENTE_MUESTRA}."
    )


def extraer_registro(ruta: Path) -> pd.DataFrame:
    """Lee el registro mercantil como texto y valida sus 25 columnas."""
    df = pd.read_excel(ruta, dtype=str)

    faltantes = [c for c in config.COLUMNAS_REGISTRO if c not in df.columns]
    if faltantes:
        raise ErrorExtraccion(
            f"{ruta.name} no tiene el esquema esperado del registro mercantil. "
            f"Columnas faltantes ({len(faltantes)}): {faltantes[:5]}..."
        )
    if df.empty:
        raise ErrorExtraccion(f"{ruta.name} no contiene registros.")

    return df[config.COLUMNAS_REGISTRO]


def extraer_ciiu() -> pd.DataFrame:
    """Lee el catálogo CIIU como texto (el encabezado está en la segunda fila)."""
    if not config.CIIU_XLSX.exists():
        raise ErrorExtraccion(f"No se encontró el catálogo CIIU en {config.CIIU_XLSX}")

    df = pd.read_excel(config.CIIU_XLSX, header=1, dtype=str)
    if df.shape[1] != len(config.COLUMNAS_CIIU):
        raise ErrorExtraccion(
            f"El catálogo CIIU debería tener {len(config.COLUMNAS_CIIU)} columnas "
            f"y tiene {df.shape[1]}."
        )
    df.columns = config.COLUMNAS_CIIU
    if df["clase"].notna().sum() == 0:
        raise ErrorExtraccion("El catálogo CIIU no contiene clases (columna 'clase' vacía).")
    return df


def ejecutar(fuente: Path | None = None) -> dict:
    """Corre la etapa completa y devuelve un resumen de lo extraído."""
    ruta = elegir_fuente(fuente)
    es_muestra = ruta.resolve() == config.FUENTE_MUESTRA.resolve()
    print(f"[Extract] Fuente del registro mercantil: {ruta.name}"
          f"{'  (MUESTRA ANONIMIZADA)' if es_muestra else '  (archivo completo)'}")

    registro = extraer_registro(ruta)
    ciiu = extraer_ciiu()

    config.RAW.mkdir(parents=True, exist_ok=True)
    registro.to_csv(config.REGISTRO_EXTRAIDO, index=False, encoding="utf-8")
    ciiu.to_csv(config.CIIU_EXTRAIDO, index=False, encoding="utf-8")

    meta = {
        "fuente_registro": ruta.name,
        "es_muestra": es_muestra,
        "filas_registro": int(len(registro)),
        "columnas_registro": int(registro.shape[1]),
        "filas_ciiu_crudas": int(len(ciiu)),
        "clases_ciiu": int(ciiu["clase"].notna().sum()),
        "fecha_extraccion": datetime.now().isoformat(timespec="seconds"),
    }
    config.EXTRACCION_META.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[Extract] Registro mercantil: {meta['filas_registro']:,} filas x {meta['columnas_registro']} columnas")
    print(f"[Extract] Catálogo CIIU: {meta['filas_ciiu_crudas']:,} filas, {meta['clases_ciiu']} clases")
    print(f"[Extract] Copias guardadas en {config.RAW}")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Etapa Extract del pipeline")
    parser.add_argument("--fuente", type=Path, default=None,
                        help="Excel del registro mercantil (por defecto: PASTO.xlsx o la muestra)")
    args = parser.parse_args()
    try:
        ejecutar(args.fuente)
    except ErrorExtraccion as e:
        print(f"[Extract] ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
