"""Orquesta el pipeline completo: Extract -> Transform -> Load -> Dashboard.

Uso (desde cualquier carpeta):
    python pipeline.py
    python pipeline.py --fuente RUTA/AL/ARCHIVO.xlsx
    python pipeline.py --sin-dashboard

Si una etapa del ETL falla, el pipeline se detiene: nunca se ejecuta una etapa con las
salidas viejas de la anterior. El dashboard es la excepción: es un producto derivado de
la base ya cargada, así que si falla (por ejemplo, porque no está instalado Plotly) se
avisa pero el ETL, que sí terminó, no se invalida.
"""
import argparse
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
from dashboard import construir_dashboard, datos as datos_dashboard  # noqa: E402
from extract import extraer  # noqa: E402
from load import cargar  # noqa: E402
from transform import transformar  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline ETL del registro mercantil de la Cámara de Comercio de Pasto")
    parser.add_argument("--fuente", type=Path, default=None,
                        help="Excel del registro mercantil (por defecto: data/raw/PASTO.xlsx o la muestra anonimizada)")
    parser.add_argument("--sin-dashboard", action="store_true", help="Ejecuta solo el ETL, sin generar el dashboard")
    args = parser.parse_args()

    # (nombre, función a ejecutar, error esperable de esa etapa)
    etapas = [
        ("Extract", lambda: extraer.ejecutar(args.fuente), extraer.ErrorExtraccion),
        ("Transform", transformar.ejecutar, transformar.ErrorTransformacion),
        ("Load", cargar.ejecutar, cargar.ErrorCarga),
    ]

    print("=" * 66)
    print(" Pipeline ETL - Registro mercantil, Cámara de Comercio de Pasto")
    print("=" * 66)

    inicio = time.perf_counter()
    meta = {}
    for nombre, ejecutar, error_esperable in etapas:
        t0 = time.perf_counter()
        try:
            resultado = ejecutar()
        except error_esperable as e:
            print(f"\n[{nombre}] ERROR: {e}")
            print(f"El pipeline se detuvo en la etapa {nombre}; no se ejecutaron las siguientes.")
            return 1
        except Exception:
            print(f"\n[{nombre}] Falla inesperada. El pipeline se detuvo; no se ejecutaron las siguientes.")
            raise
        if nombre == "Extract":
            meta = resultado
        print(f"[{nombre}] listo en {time.perf_counter() - t0:.1f} s\n")

    dashboard = None
    if not args.sin_dashboard:
        t0 = time.perf_counter()
        try:
            dashboard = construir_dashboard.ejecutar()
            print(f"[Dashboard] listo en {time.perf_counter() - t0:.1f} s\n")
        except datos_dashboard.ErrorDashboard as e:
            print(f"[Dashboard] AVISO: {e}")
            print("[Dashboard] El ETL terminó correctamente; solo falta generar el dashboard.\n")
        except Exception:
            traceback.print_exc()
            print("[Dashboard] AVISO: falla inesperada al generar el dashboard. El ETL terminó correctamente.\n")

    print("=" * 66)
    print(f" Pipeline completado en {time.perf_counter() - inicio:.1f} s")
    print(f" Fuente usada: {meta.get('fuente_registro')} "
          f"({'MUESTRA anonimizada' if meta.get('es_muestra') else 'archivo completo'}, "
          f"{meta.get('filas_registro', 0):,} registros)")
    print(f" Base de datos: {config.BASE_DATOS}")
    print(f" Reporte de calidad: {config.REPORTE_CALIDAD}")
    if args.sin_dashboard:
        print(" Dashboard: omitido (--sin-dashboard)")
    elif dashboard:
        print(f" Dashboard: {dashboard}")
    else:
        print(" Dashboard: NO generado (ver aviso arriba)")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
