import csv
import json
import math
import sys
import time
from datetime import datetime
from itertools import combinations
from pathlib import Path


def verificar_factibilidad(etapas: list, categorias_riesgo: list) -> tuple:
    """Verifica en O(n * r) si la unión de todas las interacciones cubre las r categorías."""
    universo_requerido = set(r["id"] for r in categorias_riesgo)
    universo_cubierto = set()

    for e in etapas:
        universo_cubierto.update(
            e.get("riesgos_cubiertos_auditoria_completa", [])
        )

    es_factible = universo_requerido.issubset(universo_cubierto)
    return es_factible, universo_requerido, universo_cubierto


def cobertura_voraz_set_cover(etapas: list, universo_riesgos: set) -> list:
    """Algoritmo Voraz para Cobertura de Conjuntos (Set Cover).

    Complejidad: O(n * r * min(n, r)).
    """
    pendientes = set(universo_riesgos)
    seleccionadas = []
    candidatas = [
        {
            "id": e["id"],
            "riesgos": set(e.get("riesgos_cubiertos_auditoria_completa", [])),
        }
        for e in etapas
    ]

    while pendientes:
        mejor_etapa = None
        mejor_cobertura = set()

        for c in candidatas:
            cobertura_nueva = c["riesgos"] & pendientes
            if len(cobertura_nueva) > len(mejor_cobertura):
                mejor_cobertura = cobertura_nueva
                mejor_etapa = c

        if not mejor_etapa or len(mejor_cobertura) == 0:
            break

        seleccionadas.append({
            "id": mejor_etapa["id"],
            "cobertura_nueva": list(mejor_cobertura),
            "total_cubiertos_etapa": len(mejor_etapa["riesgos"]),
        })
        pendientes -= mejor_cobertura

    return seleccionadas


def cobertura_optima_fuerza_bruta(
    etapas: list, universo_riesgos: set
) -> list:
    """Calcula la solución óptima exacta mediante fuerza bruta / combinación mínima.

    Diseñado para validación empírica en instancias pequeñas (n <= 25).
    """
    n = len(etapas)
    cand_ids = [e["id"] for e in etapas]
    cand_sets = [
        set(e.get("riesgos_cubiertos_auditoria_completa", [])) for e in etapas
    ]

    for k in range(1, n + 1):
        for combo in combinations(range(n), k):
            union_set = set()
            for idx in combo:
                union_set.update(cand_sets[idx])
            if universo_riesgos.issubset(union_set):
                return [cand_ids[idx] for idx in combo]
    return []


def ejecutar_auditoria(ruta_json: str, ruta_csv: str = None):
    with open(ruta_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    etapas = data["etapas"]
    categorias = data["categorias_riesgo"]
    n = len(etapas)
    r = len(categorias)

    # 1. Verificación de Factibilidad O(n * r)
    factible, universo_req, universo_cub = verificar_factibilidad(
        etapas, categorias
    )
    print(
        f"2. Verificación de Factibilidad O(n·r):"
        f" {'FACTIBLE' if factible else 'INFACTIBLE'}"
    )
    print(f"   • Categorías requeridas (r) : {r}")
    print(f"   • Categorías alcanzables   : {len(universo_cub)}")

    if not factible:
        faltantes = universo_req - universo_cub
        print(
            f"❌ ERROR: La instancia es INFACTIBLE. Riesgos no cubiertos:"
            f" {faltantes}"
        )
        sys.exit(1)

    # 2. Ejecución Voraz
    t0 = time.perf_counter()
    sol_voraz = cobertura_voraz_set_cover(etapas, universo_req)
    tiempo_setcover = time.perf_counter() - t0

    ids_voraz = [s["id"] for s in sol_voraz]
    d_max = max(
        len(e.get("riesgos_cubiertos_auditoria_completa", [])) for e in etapas
    )
    H_d = sum(1.0 / i for i in range(1, d_max + 1))
    H_r = sum(1.0 / i for i in range(1, r + 1))

    # 3. Validación empírica con óptimo exacto (Si n <= 25)
    sol_optima = []
    ratio = 1.0
    if n <= 25:
        sol_optima = cobertura_optima_fuerza_bruta(etapas, universo_req)
        ratio = len(ids_voraz) / len(sol_optima) if sol_optima else 1.0

    fecha_ejecucion = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    carpeta_resultados = (
        Path(__file__).resolve().parents[2]
        / "Results"
        / "ResultsPy"
        / "SetCover"
    )
    carpeta_resultados.mkdir(parents=True, exist_ok=True)
    if ruta_csv is None:
        ruta_csv = str(
            carpeta_resultados
            / f"resultados_setcover_N{n}_{fecha_ejecucion}.csv"
        )

    # 4. Guardar resultados a CSV
    with open(ruta_csv, mode="w", newline="", encoding="utf-8") as f:
        f.write(
            "orden_seleccion,id_interaccion,nuevos_riesgos_cubiertos,"
            "cantidad_nuevos_riesgos\n"
        )
        for idx, paso in enumerate(sol_voraz, 1):
            riesgos_cubiertos = ";".join(paso["cobertura_nueva"])
            f.write(
                f'{idx},{paso["id"]},"{riesgos_cubiertos}",'
                f'{len(paso["cobertura_nueva"])}\n'
            )

    # 5. Salida por Consola
    print("\n" + "=" * 65)
    print("      RESULTADOS DE COBERTURA MÍNIMA DE AUDITORÍA (SET COVER)")
    print("=" * 65)
    print(f"• Interacciones evaluadas (n)  : {n}")
    print(f"• Categorías de riesgo (r)     : {r}")
    print(f"• Máximo coberturas por nodo (d): {d_max}")
    print(
        f"• Tamaño Cobertura Voraz       : {len(ids_voraz)} interacciones"
        f" -> {ids_voraz}"
    )

    if sol_optima:
        print(
            f"• Tamaño Cobertura Óptima (FB) : {len(sol_optima)} interacciones"
            f" -> {sol_optima}"
        )
        print(f"• Ratio de Aproximación (|V|/|OPT|): {ratio:.4f}")

    print("-" * 65)
    print("VERIFICACIÓN TEOREMA 4.3.1 (COTA DE JOHNSON / CHVÁTAL):")
    print(f"  - Cota armónica H(d)         = {H_d:.4f}")
    print(f"  - Cota armónica global H(r)  = {H_r:.4f}")
    print(f"  - ¿Cumple ratio <= H(d)?     = {ratio <= H_d} ({ratio:.4f} <= {H_d:.4f})")
    print(f"• Tiempo de ejecución Voraz    : {tiempo_setcover * 1000:.3f} ms")
    print(f"• Persistencia en CSV          : {ruta_csv}")
    print("=" * 65)


if __name__ == "__main__":
    carpeta_datos = Path(__file__).resolve().parents[2] / "Test_Data"
    nombre_archivo = input(
        "Ingrese el nombre del archivo de datos de prueba "
        "(ubicado en Test_Data): "
    ).strip()
    if not nombre_archivo:
        print("Error: Debe ingresar el nombre de un archivo de prueba.")
        sys.exit(1)

    archivo_input = carpeta_datos / Path(nombre_archivo).name
    if not archivo_input.is_file():
        print(
            f"Error: No se encontró el archivo de prueba en Test_Data: "
            f"{archivo_input.name}"
        )
        sys.exit(1)

    ejecutar_auditoria(str(archivo_input))