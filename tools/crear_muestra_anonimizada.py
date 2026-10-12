"""Genera una muestra anonimizada del registro mercantil para subir al repositorio.

Uso:
    python tools/crear_muestra_anonimizada.py RUTA_AL_EXCEL_COMPLETO [--n 1000]

Qué hace:
  - Toma una muestra aleatoria reproducible (semilla fija) de n registros.
  - Conserva las 25 columnas originales, en el mismo orden, para que el pipeline
    funcione igual con la muestra o con el archivo completo.
  - Vacía las columnas con datos personales o de contacto del propietario y las
    direcciones, y reemplaza la matrícula y la razón social por seudónimos.

El archivo completo NO debe subirse al repositorio (ver .gitignore).
"""
import argparse
from pathlib import Path

import pandas as pd

SEMILLA = 42

# Columnas que se vacían: datos personales/de contacto del propietario y direcciones.
COLUMNAS_A_VACIAR = [
    "DIR-COMERCIAL", "DIR-NOTIFICACION",
    "MAT-PROP.", "IDE-PROP.", "NIT-PROP.", "CAM-PROP.", "NOM-PROP",
    "DIR-PROP", "TEL-1-PROP", "TEL-2-PROP", "MUN-PROP",
]

SALIDA = Path(__file__).resolve().parent.parent / "data" / "raw" / "muestra_anonimizada.xlsx"


def crear_muestra(ruta_completa: Path, n: int) -> pd.DataFrame:
    df = pd.read_excel(ruta_completa)
    columnas = list(df.columns)

    muestra = df.sample(n=min(n, len(df)), random_state=SEMILLA).reset_index(drop=True)

    # Seudónimos: no se puede volver al registro original desde la muestra.
    muestra["MATRICULA"] = range(1, len(muestra) + 1)
    muestra["RAZON SOCIAL"] = [f"EMPRESA {i:04d}" for i in range(1, len(muestra) + 1)]

    for col in COLUMNAS_A_VACIAR:
        muestra[col] = pd.NA

    return muestra[columnas]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("ruta", type=Path, help="Excel completo del registro mercantil")
    parser.add_argument("--n", type=int, default=1000, help="Tamaño de la muestra")
    args = parser.parse_args()

    muestra = crear_muestra(args.ruta, args.n)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    muestra.to_excel(SALIDA, index=False)
    print(f"Muestra anonimizada: {len(muestra)} filas x {muestra.shape[1]} columnas -> {SALIDA}")


if __name__ == "__main__":
    main()
