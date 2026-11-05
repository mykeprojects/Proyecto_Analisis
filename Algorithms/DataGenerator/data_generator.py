import json
import random
from datetime import datetime
from pathlib import Path


def generar_datos_prueba(
    numero_etapas: int,
    ruta_salida: str = None,
    porcentaje_presupuesto: float = 0.35,
):
    """Genera una estructura de datos sintética y la guarda en un archivo .json en Windows.

    :param numero_etapas: Cantidad de etapas a generar (ej. 1000, 2000, 3000).
    :param ruta_salida: Nombre opcional del archivo de salida .json.
    :param porcentaje_presupuesto: Porcentaje del costo total para asignar al
    presupuesto B.
    """
    carpeta_salida = Path(__file__).resolve().parents[2] / "Test_Data"
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    nombre_base = (
        Path(ruta_salida).name
        if ruta_salida
        else f"Test_Data_{numero_etapas}_nodos.json"
    )
    nombre_archivo = Path(nombre_base)
    fecha_creacion = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    ruta_salida = (
        carpeta_salida
        / f"{nombre_archivo.stem}_{fecha_creacion}{nombre_archivo.suffix or '.json'}"
    )

    # Relación 80/100: Número de riesgos es el 80% del total de etapas
    numero_riesgos = max(1, int(numero_etapas * 0.80))

    nombres_categorias = [
        "sesgo",
        "privacidad",
        "formato",
        "seguridad",
        "trazabilidad",
        "equidad",
        "coherencia",
        "robustez",
        "disponibilidad",
        "cumplimiento",
        "integridad",
        "transparencia",
    ]

    digitos_e = max(2, len(str(numero_etapas)))
    digitos_r = max(2, len(str(numero_riesgos)))

    # 1. Categorías de Riesgo
    categorias_riesgo = [
        {
            "id": f"R{i:0{digitos_r}d}",
            "categoria": random.choice(nombres_categorias),
            "importancia": random.randint(1, 5),
        }
        for i in range(1, numero_riesgos + 1)
    ]
    ids_riesgos = [r["id"] for r in categorias_riesgo]

    # 2. Flujo Secuencial
    flujo = [
        {"origen": f"E{i:0{digitos_e}d}", "destino": f"E{i + 1:0{digitos_e}d}"}
        for i in range(1, numero_etapas)
    ]

    # 3. Etapas y Auditorías
    etapas = []
    costo_aceleracion_total = 0

    for i in range(1, numero_etapas + 1):
        id_etapa = f"E{i:0{digitos_e}d}"
        duracion_normal = random.randint(15, 35)
        costo_aceleracion = random.randint(5, 18)
        reduccion_tiempo = random.randint(
            3, max(3, min(duracion_normal - 5, costo_aceleracion + 2))
        )

        riesgos_completa = random.sample(
            ids_riesgos, min(len(ids_riesgos), random.randint(2, 5))
        )
        riesgos_parcial = riesgos_completa[: max(1, len(riesgos_completa) // 2)]

        c_completa = random.randint(5, 10)
        c_parcial = random.randint(2, max(2, c_completa - 2))

        etapas.append({
            "id": id_etapa,
            "duracion_normal": duracion_normal,
            "costo_aceleracion": costo_aceleracion,
            "reduccion_tiempo_si_acelera": reduccion_tiempo,
            "riesgos_cubiertos_auditoria_completa": riesgos_completa,
            "variaciones_auditoria": [
                {
                    "id": "parcial",
                    "costo": c_parcial,
                    "riesgos_cubiertos": riesgos_parcial,
                },
                {
                    "id": "completa",
                    "costo": c_completa,
                    "riesgos_cubiertos": riesgos_completa,
                },
            ],
        })
        costo_aceleracion_total += costo_aceleracion

    # 4. Cálculo del Presupuesto B
    presupuesto_b = int(costo_aceleracion_total * porcentaje_presupuesto)
    presupuesto_conjunto = int(presupuesto_b * 1.4)

    estructura_datos = {
        "parametros": {
            "numero_etapas": numero_etapas,
            "presupuesto_aceleracion_B": presupuesto_b,
            "presupuesto_conjunto_aceleracion_y_auditoria": presupuesto_conjunto,
            "numero_categorias_riesgo": numero_riesgos,
        },
        "flujo": flujo,
        "categorias_riesgo": categorias_riesgo,
        "etapas": etapas,
    }

    # 5. Guardar archivo JSON en disco (Compatible con Windows UTF-8)
    with ruta_salida.open("w", encoding="utf-8") as file:
        json.dump(estructura_datos, file, indent=2, ensure_ascii=False)

    print("\n" + "=" * 55)
    print("      ¡ARCHIVO JSON GENERADO CON ÉXITO EN WINDOWS!")
    print("=" * 55)
    print(f" • Ubicación del archivo : {ruta_salida}")
    print(f" • Número de etapas (N)  : {numero_etapas}")
    print(f" • Categorías de riesgo  : {numero_riesgos} (Relación 80/100)")
    print(f" • Presupuesto B (0/1 DP): {presupuesto_b}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    try:
        etapas_input = input(
            "Ingrese la cantidad de etapas a generar (ej: 1000, 2000,"
            " 3000) [Por defecto: 1000]: "
        ).strip()
        num_etapas = int(etapas_input) if etapas_input else 1000

        nombre_archivo = input(
            "Ingrese el nombre del archivo .json [Presione ENTER para el nombre"
            " automático]: "
        ).strip()
        ruta = nombre_archivo if nombre_archivo else None

        generar_datos_prueba(num_etapas, ruta)
    except ValueError:
        print("\nError: Debe ingresar un número entero válido.")