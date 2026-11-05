import csv
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter


def cargar_datos_json(ruta_archivo: str) -> dict:
    """Lee el archivo JSON de entrada y extrae la información requerida

    para la optimización de la mochila (aceleración de etapas).
    """
    with open(ruta_archivo, "r", encoding="utf-8") as file:
        data = json.load(file)

    presupuesto_b = data["parametros"]["presupuesto_aceleracion_B"]
    etapas_preparadas = []

    for etapa in data["etapas"]:
        etapas_preparadas.append({
            "id": etapa["id"],
            "duracion_normal": etapa["duracion_normal"],
            "costo": etapa["costo_aceleracion"],
            "reduccion": etapa["reduccion_tiempo_si_acelera"],
        })

    return {"presupuesto_B": presupuesto_b, "etapas": etapas_preparadas}


def optimizar_aceleracion_mochila(datos_preparados: dict) -> dict:
    """Resuelve el problema de la mochila 0/1 aplicando programación dinámica.

    Rastrea la simulación cronológica del presupuesto de E01 a E20.
    """
    presupuesto_max = datos_preparados["presupuesto_B"]
    etapas = datos_preparados["etapas"]
    n = len(etapas)

    inicio_programacion_dinamica = perf_counter()
    # 1. Matriz DP[i][w]
    dp = [[0] * (presupuesto_max + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        costo = etapas[i - 1]["costo"]
        reduccion = etapas[i - 1]["reduccion"]
        for w in range(presupuesto_max + 1):
            if costo <= w:
                dp[i][w] = max(dp[i - 1][w], dp[i - 1][w - costo] + reduccion)
            else:
                dp[i][w] = dp[i - 1][w]
    tiempo_programacion_dinamica = perf_counter() - inicio_programacion_dinamica

    # 2. Backtracking para determinar qué etapas se aceleran (Evaluando de E20 a E01)
    w = presupuesto_max
    decisiones = [False] * n

    for i in range(n, 0, -1):
        if dp[i][w] != dp[i - 1][w]:
            decisiones[i - 1] = True
            w -= etapas[i - 1]["costo"]

    # 3. Simulación Cronológica Progresiva (Recorriendo de E01 a E20)
    presupuesto_disponible = presupuesto_max
    pasos_reconstruccion = []
    etapas_seleccionadas = []

    for i in range(n):
        etapa_actual = etapas[i]
        acelerar = decisiones[i]
        costo = etapa_actual["costo"] if acelerar else 0
        reduccion = etapa_actual["reduccion"] if acelerar else 0
        duracion_final_etapa = etapa_actual["duracion_normal"] - reduccion

        presupuesto_antes = presupuesto_disponible
        presupuesto_despues = presupuesto_disponible - costo
        presupuesto_disponible = presupuesto_despues  # Se actualiza para el siguiente paso

        if acelerar:
            etapas_seleccionadas.append(etapa_actual["id"])

        pasos_reconstruccion.append({
            "id_etapa": etapa_actual["id"],
            "duracion_normal": etapa_actual["duracion_normal"],
            "duracion_final": duracion_final_etapa,
            "decision": "ACELERAR" if acelerar else "NO ACELERAR",
            "costo_aceleracion": costo,
            "reduccion_obtenida": reduccion,
            "presupuesto_disponible_antes": presupuesto_antes,
            "presupuesto_restante_despues": presupuesto_despues,
        })

    # 4. Cálculo de Totales
    duracion_inicial_total = sum(e["duracion_normal"] for e in etapas)
    reduccion_lograda_total = dp[n][presupuesto_max]
    duracion_final_total = duracion_inicial_total - reduccion_lograda_total
    costo_acumulado_total = sum(p["costo_aceleracion"] for p in pasos_reconstruccion)

    resumen = {
        "duracion_inicial_total": duracion_inicial_total,
        "reduccion_lograda_total": reduccion_lograda_total,
        "duracion_final_total": duracion_final_total,
        "costo_acumulado_total": costo_acumulado_total,
        "presupuesto_maximo_B": presupuesto_max,
        "etapas_seleccionadas": etapas_seleccionadas,
        "eficiencia_global": (
            round(reduccion_lograda_total / costo_acumulado_total, 4)
            if costo_acumulado_total > 0
            else 0
        ),
    }

    return {
        "resumen": resumen,
        "detalle_etapas": pasos_reconstruccion,
        "tiempo_programacion_dinamica": tiempo_programacion_dinamica,
    }


def guardar_resultados_csv(
    resultados: dict, ruta_csv: str
) -> None:
    """Persiste el historial de decisiones por etapa en formato CSV."""
    columnas = [
        "id_etapa",
        "duracion_normal",
        "duracion_final",
        "decision",
        "costo_aceleracion",
        "reduccion_obtenida",
        "presupuesto_disponible_antes",
        "presupuesto_restante_despues",
    ]

    with open(ruta_csv, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columnas)
        writer.writeheader()
        for fila in resultados["detalle_etapas"]:
            writer.writerow(fila)


def guardar_resumen_csv(
    resultados: dict, ruta_csv: Path
) -> None:
    """Persiste el resumen de la optimización en formato CSV."""
    resumen = resultados["resumen"]
    columnas = [
        "duracion_inicial_total",
        "reduccion_lograda_total",
        "duracion_final_total",
        "costo_acumulado_total",
        "presupuesto_maximo_B",
        "etapas_seleccionadas",
        "eficiencia_global",
        "tiempo_programacion_dinamica",
    ]

    with ruta_csv.open(mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columnas)
        writer.writeheader()
        writer.writerow({
            "duracion_inicial_total": resumen["duracion_inicial_total"],
            "reduccion_lograda_total": resumen["reduccion_lograda_total"],
            "duracion_final_total": resumen["duracion_final_total"],
            "costo_acumulado_total": resumen["costo_acumulado_total"],
            "presupuesto_maximo_B": resumen["presupuesto_maximo_B"],
            "etapas_seleccionadas": "|".join(resumen["etapas_seleccionadas"]),
            "eficiencia_global": resumen["eficiencia_global"],
            "tiempo_programacion_dinamica": (
                resultados["tiempo_programacion_dinamica"]
            ),
        })


def ejecutar_pipeline(
    ruta_json_entrada: str, directorio_salida: str = None
) -> dict:
    """Ejecuta el pipeline y exporta la solución identificada por fecha y hora."""
    datos = cargar_datos_json(ruta_json_entrada)

    resultados = optimizar_aceleracion_mochila(datos)

    if directorio_salida is None:
        directorio_salida = (
            Path(__file__).resolve().parents[2]
            / "Results"
            / "ResultsPy"
            / "Aceleracion"
        )
    Path(directorio_salida).mkdir(parents=True, exist_ok=True)
    fecha_ejecucion = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    cantidad_nodos = len(resultados["detalle_etapas"])
    ruta_csv_salida = (
        Path(directorio_salida)
        / f"resultados_aceleracion_N{cantidad_nodos}_{fecha_ejecucion}.csv"
    )
    ruta_csv_resumen = (
        Path(directorio_salida)
        / f"resumen_optimizacion_N{cantidad_nodos}_{fecha_ejecucion}.csv"
    )
    guardar_resultados_csv(resultados, ruta_csv_salida)
    guardar_resumen_csv(resultados, ruta_csv_resumen)

    resumen = resultados["resumen"]
    print(
        "Tiempo de programación dinámica: "
        f"{resultados['tiempo_programacion_dinamica']:.9f} segundos"
    )
    print("\nRESUMEN DE LA OPTIMIZACIÓN")
    print(f"Duración inicial total: {resumen['duracion_inicial_total']}")
    print(f"Reducción lograda total: {resumen['reduccion_lograda_total']}")
    print(f"Duración final total: {resumen['duracion_final_total']}")
    print(f"Costo total: {resumen['costo_acumulado_total']}")
    print(f"Etapas seleccionadas: {resumen['etapas_seleccionadas']}")
    print(f"Eficiencia (red/costo): {resumen['eficiencia_global']}")
    print(f"Solución exportada: {ruta_csv_salida}")
    print(f"Resumen exportado: {ruta_csv_resumen}")

    return resultados


def seleccionar_datos_prueba() -> Path:
    """Solicita el nombre del archivo y lo resuelve dentro de Test_Data."""
    carpeta_datos = Path(__file__).resolve().parents[2] / "Test_Data"
    nombre_archivo = input(
        "Ingrese el nombre del archivo de datos de prueba "
        "(ubicado en Test_Data): "
    ).strip()

    if not nombre_archivo:
        raise ValueError("Debe ingresar el nombre de un archivo de prueba.")

    ruta_archivo = carpeta_datos / Path(nombre_archivo).name
    if not ruta_archivo.is_file():
        raise FileNotFoundError(
            f"No se encontró el archivo de prueba en Test_Data: {ruta_archivo.name}"
        )

    return ruta_archivo


if __name__ == "__main__":
    try:
        ejecutar_pipeline(str(seleccionar_datos_prueba()))
    except (ValueError, FileNotFoundError) as error:
        print(f"Error: {error}")