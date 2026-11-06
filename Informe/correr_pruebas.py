"""Repite las pruebas del informe en esta máquina.

Genera las instancias, corre la mochila y el set cover en Python y en C++,
deja los CSV en Results/ y dibuja cuatro gráficas nuevas.

Desde la raíz del proyecto:

    python Informe/correr_pruebas.py

Hace falta g++ en el PATH y matplotlib (pip install matplotlib).
La corrida de n = 3000 puede tardar varios minutos.
"""

import csv
import importlib.util
import json
import platform
import random
import re
import subprocess
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
PY_DIR = ROOT / "Algorithms" / "AlgorithmsPy"
GEN_DIR = ROOT / "Algorithms" / "DataGenerator"
CPP_DIR = ROOT / "Algorithms" / "AlgorithmsCpp"
TEST_DATA = ROOT / "Test_Data"
DATOS = Path(__file__).resolve().parent / "datos"
GRAFICAS = Path(__file__).resolve().parent / "graficas"

SIZES = [250, 500, 1000, 1500, 2000, 3000]
REPS = 3
SEED = 20261105


def load_module(alias: str, path: Path):
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def newest(directory: Path, pattern: str) -> Path:
    files = list(directory.glob(pattern))
    if not files:
        raise FileNotFoundError(pattern)
    return max(files, key=lambda item: item.stat().st_mtime)


def compile_cpp() -> tuple[Path, Path]:
    knapsack = CPP_DIR / "0_1_knapsack.exe"
    cover = CPP_DIR / "set_cover.exe"
    sources = [
        (CPP_DIR / "0_1_knapsack.cpp", knapsack),
        (CPP_DIR / "set_cover.cpp", cover),
    ]
    for source, binary in sources:
        subprocess.run(
            ["g++", "-std=c++17", "-O3", str(source), "-o", str(binary)],
            check=True,
            cwd=ROOT,
        )
    return knapsack, cover


def run_cpp(exe: Path, filename: str) -> str:
    completed = subprocess.run(
        [str(exe)],
        input=filename + "\n",
        text=True,
        capture_output=True,
        cwd=ROOT,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)
    return completed.stdout


def parse_float(pattern: str, text: str) -> float:
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"No se encontró el patrón {pattern}")
    return float(match.group(1))


def reparar_cobertura(instance: Path) -> int:
    """El generador no garantiza cubrir las r categorías.

    Cada riesgo que quede fuera se agrega a una etapa al azar. Sin eso el
    set cover se detiene y no hay tiempo que medir.
    """
    with instance.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    requeridos = {item["id"] for item in raw["categorias_riesgo"]}
    cubiertos = set()
    for etapa in raw["etapas"]:
        cubiertos.update(etapa.get("riesgos_cubiertos_auditoria_completa", []))
    faltantes = list(requeridos - cubiertos)
    for riesgo in faltantes:
        etapa = random.choice(raw["etapas"])
        etapa["riesgos_cubiertos_auditoria_completa"].append(riesgo)
    if faltantes:
        with instance.open("w", encoding="utf-8") as handle:
            json.dump(raw, handle, indent=2, ensure_ascii=False)
    return len(faltantes)


def call_quiet(function, *args):
    captured = StringIO()
    previous = sys.stdout
    sys.stdout = captured
    try:
        result = function(*args)
    finally:
        sys.stdout = previous
    return result, captured.getvalue()


def draw(summary: list[dict], folder: Path) -> None:
    import matplotlib.pyplot as plt

    folder.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Serif",
            "font.size": 11,
            "axes.labelsize": 12,
            "legend.fontsize": 10,
            "figure.figsize": (7.4, 4.3),
            "axes.grid": True,
            "grid.alpha": 0.35,
            "axes.axisbelow": True,
        }
    )
    sizes = [item["n"] for item in summary]
    series = [
        (
            "mochila_tiempo.jpg",
            [item["py_mochila"] * 1000 for item in summary],
            [item["cpp_mochila"] * 1000 for item in summary],
            "Número de etapas  n",
            "Tiempo mediano (ms)",
            True,
        ),
        (
            "mochila_por_celda.jpg",
            [item["py_mochila"] / item["celdas"] * 1e9 for item in summary],
            [item["cpp_mochila"] / item["celdas"] * 1e9 for item in summary],
            "Número de etapas  n",
            "Tiempo / (n · B)   (ns por celda)",
            True,
        ),
        (
            "setcover_tiempo.jpg",
            [item["py_cover"] * 1000 for item in summary],
            [item["cpp_cover"] * 1000 for item in summary],
            "Número de interacciones  n",
            "Tiempo mediano (ms)",
            False,
        ),
        (
            "setcover_por_n2.jpg",
            [item["py_cover"] / item["n"] ** 2 * 1e9 for item in summary],
            [item["cpp_cover"] / item["n"] ** 2 * 1e9 for item in summary],
            "Número de interacciones  n",
            "Tiempo / n²   (ns)",
            False,
        ),
    ]
    for name, py_values, cpp_values, xlabel, ylabel, log_y in series:
        figure, axis = plt.subplots()
        axis.plot(sizes, py_values, "o-", color="#C45911", label="Python")
        axis.plot(sizes, cpp_values, "s-", color="#1F4E79", label="C++")
        axis.set_xlabel(xlabel)
        axis.set_ylabel(ylabel)
        if log_y:
            axis.set_yscale("log")
        axis.legend()
        figure.tight_layout()
        figure.savefig(folder / name, dpi=160)
        plt.close(figure)


def main() -> None:
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        print("Falta matplotlib. Instálalo con: pip install matplotlib")
        sys.exit(1)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    machine = platform.node() or "maquina"
    run_name = f"{stamp}_{machine}"
    graph_dir = GRAFICAS / run_name
    DATOS.mkdir(parents=True, exist_ok=True)

    knapsack_py = load_module("knapsack_py", PY_DIR / "0_1_knapsack.py")
    cover_py = load_module("cover_py", PY_DIR / "set_cover.py")
    generator = load_module("generator", GEN_DIR / "data_generator.py")
    print("Compilando C++ con g++ -std=c++17 -O3 ...")
    knapsack_exe, cover_exe = compile_cpp()

    rows = []
    for size in SIZES:
        used_seed = SEED + size
        random.seed(used_seed)
        generator.generar_datos_prueba(size, f"bench_N{size:04d}.json")
        instance = newest(TEST_DATA, f"bench_N{size:04d}_*.json")
        reparados = reparar_cobertura(instance)

        with instance.open(encoding="utf-8") as handle:
            raw = json.load(handle)
        budget = raw["parametros"]["presupuesto_aceleracion_B"]
        risks = len(raw["categorias_riesgo"])
        print(
            f"n={size} B={budget} r={risks} semilla={used_seed} "
            f"riesgos_agregados={reparados}"
        )

        for rep in range(1, REPS + 1):
            print(f"  repeticion={rep}", flush=True)
            py_pack, _ = call_quiet(
                knapsack_py.ejecutar_pipeline, str(instance)
            )
            cpp_pack_out = run_cpp(knapsack_exe, instance.name)
            _, cover_out = call_quiet(
                cover_py.ejecutar_auditoria, str(instance)
            )
            cpp_cover_out = run_cpp(cover_exe, instance.name)

            py_cover_size = int(
                parse_float(
                    r"Tama[nñ]o Cobertura Voraz\s*:\s+(\d+)", cover_out
                )
            )
            rows.append(
                {
                    "n": size,
                    "semilla": used_seed,
                    "riesgos_agregados": reparados,
                    "repeticion": rep,
                    "maquina": machine,
                    "B": budget,
                    "r": risks,
                    "celdas": size * budget,
                    "py_mochila_s": py_pack["tiempo_programacion_dinamica"],
                    "cpp_mochila_s": parse_float(
                        r"Tiempo de programaci[oó]n din[aá]mica:\s+([0-9.]+)",
                        cpp_pack_out,
                    ),
                    "py_reduccion": py_pack["resumen"]["reduccion_lograda_total"],
                    "cpp_reduccion": int(
                        parse_float(
                            r"Reducci[oó]n lograda total:\s+(\d+)", cpp_pack_out
                        )
                    ),
                    "py_setcover_s": parse_float(
                        r"Tiempo de ejecuci[oó]n Voraz\s*:\s+([0-9.]+)",
                        cover_out,
                    )
                    / 1000.0,
                    "cpp_setcover_s": parse_float(
                        r"Tiempo de ejecuci[oó]n Voraz\s*:\s+([0-9.]+)",
                        cpp_cover_out,
                    )
                    / 1000.0,
                    "py_cover_size": py_cover_size,
                    "cpp_cover_size": int(
                        parse_float(
                            r"Tama[nñ]o Cobertura Voraz\s*:\s+(\d+)",
                            cpp_cover_out,
                        )
                    ),
                    "instancia": instance.name,
                }
            )

    csv_path = DATOS / f"tiempos_{run_name}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    grouped: dict[int, list] = {}
    for row in rows:
        grouped.setdefault(row["n"], []).append(row)
    summary = []
    for size in SIZES:
        group = grouped[size]
        first = group[0]
        summary.append(
            {
                "n": size,
                "celdas": first["celdas"],
                "py_mochila": median(item["py_mochila_s"] for item in group),
                "cpp_mochila": median(item["cpp_mochila_s"] for item in group),
                "py_cover": median(item["py_setcover_s"] for item in group),
                "cpp_cover": median(item["cpp_setcover_s"] for item in group),
            }
        )
    draw(summary, graph_dir)

    print()
    print(f"Datos:     {csv_path}")
    print(f"Graficas:  {graph_dir}")
    print("Resultados: Results/ResultsPy y Results/ResultsCpp")
    print("Instancias: Test_Data/bench_N*.json")
    print(
        "Las cuatro JPG del informe no se reemplazan. "
        "Estas gráficas son las de esta máquina."
    )


if __name__ == "__main__":
    main()
