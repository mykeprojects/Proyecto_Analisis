#define NOMINMAX
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <iomanip>
#include <sstream>
#include <algorithm>
#include <chrono>
#include <ctime>
#include <filesystem>

// Configuración de UTF-8 para consola en Windows
#ifdef _WIN32
#include <windows.h>
#endif

// Estructura para representar los datos de cada etapa
struct Etapa {
    std::string id;
    int duracion_normal;
    int costo_aceleracion;
    int reduccion_tiempo;
};

// Estructura para registrar la simulación paso a paso
struct PasoReconstruccion {
    std::string id_etapa;
    int duracion_normal;
    int duracion_final;
    std::string decision;
    int costo_aceleracion;
    int reduccion_obtenida;
    int presupuesto_antes;
    int presupuesto_despues;
};

// Estructura para almacenar las métricas agregadas
struct ResumenOptimizacion {
    int duracion_inicial_total;
    int reduccion_lograda_total;
    int duracion_final_total;
    int costo_acumulado_total;
    int presupuesto_maximo_B;
    std::vector<std::string> etapas_seleccionadas;
    double eficiencia_global;
};

struct ResultadoPipeline {
    ResumenOptimizacion resumen;
    std::vector<PasoReconstruccion> detalle_etapas;
    double tiempo_programacion_dinamica;
};

// Función auxiliar para extraer enteros de cualquier campo JSON
int extraerIntJson(const std::string& texto, const std::string& clave, size_t offset = 0) {
    size_t pos = texto.find("\"" + clave + "\"", offset);
    if (pos == std::string::npos) return 0;
    size_t pos_col = texto.find(":", pos);
    if (pos_col == std::string::npos) return 0;
    size_t pos_val = texto.find_first_of("0123456789", pos_col);
    if (pos_val == std::string::npos) return 0;
    return std::stoi(texto.substr(pos_val));
}

// 1. Carga de datos JSON tolerante a cualquier sangría o salto de línea
bool cargarDatosJSON(const std::string& ruta_archivo, int& presupuesto_b, std::vector<Etapa>& etapas) {
    std::ifstream archivo(ruta_archivo);
    if (!archivo.is_open()) {
        std::cerr << "Error: No se pudo abrir el archivo " << ruta_archivo << std::endl;
        return false;
    }

    std::stringstream buffer;
    buffer << archivo.rdbuf();
    std::string contenido = buffer.str();
    archivo.close();

    // Extraer presupuesto B
    presupuesto_b = extraerIntJson(contenido, "presupuesto_aceleracion_B");

    // Ubicar la sección "etapas"
    size_t pos_etapas = contenido.find("\"etapas\"");
    if (pos_etapas == std::string::npos) return false;

    // Recorrer ubicando cada "duracion_normal" para identificar los bloques de etapas
    size_t pos_curr = pos_etapas;
    while ((pos_curr = contenido.find("\"duracion_normal\"", pos_curr)) != std::string::npos) {
        size_t pos_start_obj = contenido.rfind("{", pos_curr);
        size_t pos_end_obj = contenido.find("}", pos_curr);

        if (pos_start_obj != std::string::npos && pos_end_obj != std::string::npos) {
            std::string bloque = contenido.substr(pos_start_obj, pos_end_obj - pos_start_obj + 1);

            size_t id_pos = bloque.find("\"id\"");
            std::string id_str = "";
            if (id_pos != std::string::npos) {
                size_t start_q = bloque.find("\"", bloque.find(":", id_pos));
                size_t end_q = bloque.find("\"", start_q + 1);
                id_str = bloque.substr(start_q + 1, end_q - start_q - 1);
            }

            int d_normal = extraerIntJson(bloque, "duracion_normal");
            int c_acel = extraerIntJson(bloque, "costo_aceleracion");
            int r_tiempo = extraerIntJson(bloque, "reduccion_tiempo_si_acelera");

            if (!id_str.empty()) {
                etapas.push_back({id_str, d_normal, c_acel, r_tiempo});
            }
        }
        pos_curr = pos_end_obj + 1;
    }

    return !etapas.empty();
}

// 2. Algoritmo de la Mochila DP
ResultadoPipeline optimizarAceleracionMochila(int presupuesto_max, const std::vector<Etapa>& etapas) {
    int n = static_cast<int>(etapas.size());

    auto inicio_programacion_dinamica = std::chrono::high_resolution_clock::now();
    // Matriz DP[n+1][presupuesto_max+1]
    std::vector<std::vector<int>> dp(n + 1, std::vector<int>(presupuesto_max + 1, 0));

    for (int i = 1; i <= n; ++i) {
        int costo = etapas[i - 1].costo_aceleracion;
        int reduccion = etapas[i - 1].reduccion_tiempo;
        for (int w = 0; w <= presupuesto_max; ++w) {
            if (costo <= w) {
                dp[i][w] = std::max(dp[i - 1][w], dp[i - 1][w - costo] + reduccion);
            } else {
                dp[i][w] = dp[i - 1][w];
            }
        }
    }
    auto fin_programacion_dinamica = std::chrono::high_resolution_clock::now();
    double tiempo_programacion_dinamica =
        std::chrono::duration<double>(fin_programacion_dinamica - inicio_programacion_dinamica).count();

    // Backtracking de decisiones (de E20 a E01)
    int w = presupuesto_max;
    std::vector<bool> decisiones(n, false);
    for (int i = n; i > 0; --i) {
        if (dp[i][w] != dp[i - 1][w]) {
            decisiones[i - 1] = true;
            w -= etapas[i - 1].costo_aceleracion;
        }
    }

    // Simulación cronológica progresiva (de E01 a E20)
    int presupuesto_disponible = presupuesto_max;
    std::vector<PasoReconstruccion> pasos;
    std::vector<std::string> seleccionadas;

    int duracion_inicial_total = 0;
    int costo_acumulado_total = 0;

    for (int i = 0; i < n; ++i) {
        const auto& etapa = etapas[i];
        bool acelerar = decisiones[i];
        int costo = acelerar ? etapa.costo_aceleracion : 0;
        int reduccion = acelerar ? etapa.reduccion_tiempo : 0;
        int duracion_final = etapa.duracion_normal - reduccion;

        int p_antes = presupuesto_disponible;
        int p_despues = presupuesto_disponible - costo;
        presupuesto_disponible = p_despues;

        duracion_inicial_total += etapa.duracion_normal;
        costo_acumulado_total += costo;

        if (acelerar) {
            seleccionadas.push_back(etapa.id);
        }

        pasos.push_back({
            etapa.id,
            etapa.duracion_normal,
            duracion_final,
            acelerar ? "ACELERAR" : "NO ACELERAR",
            costo,
            reduccion,
            p_antes,
            p_despues
        });
    }

    int reduccion_lograda_total = dp[n][presupuesto_max];
    int duracion_final_total = duracion_inicial_total - reduccion_lograda_total;
    double eficiencia = (costo_acumulado_total > 0) 
        ? static_cast<double>(reduccion_lograda_total) / costo_acumulado_total 
        : 0.0;

    ResumenOptimizacion resumen = {
        duracion_inicial_total,
        reduccion_lograda_total,
        duracion_final_total,
        costo_acumulado_total,
        presupuesto_max,
        seleccionadas,
        eficiencia
    };

    return {resumen, pasos, tiempo_programacion_dinamica};
}

std::string generarMarcaTiempo() {
    auto ahora = std::chrono::system_clock::now();
    auto tiempo = std::chrono::system_clock::to_time_t(ahora);
    auto micros = std::chrono::duration_cast<std::chrono::microseconds>(
        ahora.time_since_epoch()).count() % 1000000;

    std::tm tiempo_local{};
#ifdef _WIN32
    localtime_s(&tiempo_local, &tiempo);
#else
    localtime_r(&tiempo, &tiempo_local);
#endif

    std::ostringstream id;
    id << std::put_time(&tiempo_local, "%Y%m%d_%H%M%S")
       << "_" << std::setw(6) << std::setfill('0') << micros;
    return id.str();
}

// 3. Persistencia de la solución en CSV
void guardarResultadosCSV(
    const ResultadoPipeline& resultado,
    const std::string& ruta_csv
) {
    std::ofstream archivo(ruta_csv);
    if (!archivo.is_open()) {
        std::cerr << "Error al abrir el archivo CSV para escritura." << std::endl;
        return;
    }

    archivo << "id_etapa,duracion_normal,duracion_final,decision,"
               "costo_aceleracion,reduccion_obtenida,presupuesto_disponible_antes,"
               "presupuesto_restante_despues\n";

    for (const auto& p : resultado.detalle_etapas) {
        archivo << p.id_etapa << ","
                << p.duracion_normal << ","
                << p.duracion_final << ","
                << p.decision << ","
                << p.costo_aceleracion << ","
                << p.reduccion_obtenida << ","
                << p.presupuesto_antes << ","
                << p.presupuesto_despues << "\n";
    }

    archivo.close();
}

// 4. Persistencia del resumen en CSV
void guardarResumenCSV(
    const ResultadoPipeline& resultado,
    const std::string& ruta_csv
) {
    std::ofstream archivo(ruta_csv);
    if (!archivo.is_open()) {
        std::cerr << "Error al abrir el archivo CSV de resumen para escritura." << std::endl;
        return;
    }

    const auto& res = resultado.resumen;
    archivo << "duracion_inicial_total,reduccion_lograda_total,"
               "duracion_final_total,costo_acumulado_total,presupuesto_maximo_B,"
               "etapas_seleccionadas,eficiencia_global,"
               "tiempo_programacion_dinamica\n";
    archivo << res.duracion_inicial_total << ","
            << res.reduccion_lograda_total << ","
            << res.duracion_final_total << ","
            << res.costo_acumulado_total << ","
            << res.presupuesto_maximo_B << ",";

    for (size_t i = 0; i < res.etapas_seleccionadas.size(); ++i) {
        if (i > 0) archivo << "|";
        archivo << res.etapas_seleccionadas[i];
    }

    archivo << "," << std::fixed << std::setprecision(4)
            << res.eficiencia_global << ","
            << std::setprecision(9)
            << resultado.tiempo_programacion_dinamica << "\n";
    archivo.close();
}

int main() {
    // Activar soporte UTF-8 en Windows
    #ifdef _WIN32
    SetConsoleOutputCP(CP_UTF8);
    #endif

    namespace fs = std::filesystem;
    std::string nombre_archivo;
    std::cout << "Ingrese el nombre del archivo de datos de prueba "
                 "(ubicado en Test_Data): ";
    std::getline(std::cin, nombre_archivo);

    if (nombre_archivo.empty()) {
        std::cerr << "Error: Debe ingresar el nombre de un archivo de prueba." << std::endl;
        return 1;
    }

    fs::path nombre_seguro = fs::path(nombre_archivo).filename();
    std::vector<fs::path> carpetas_datos = {
        fs::path("Test_Data"),
        fs::path("../Test_Data"),
        fs::path("../../Test_Data")
    };
    fs::path ruta_json;
    for (const auto& carpeta : carpetas_datos) {
        fs::path candidato = carpeta / nombre_seguro;
        if (fs::is_regular_file(candidato)) {
            ruta_json = candidato;
            break;
        }
    }

    if (ruta_json.empty()) {
        std::cerr << "Error: No se encontró el archivo de prueba en Test_Data: "
                  << nombre_seguro.string() << std::endl;
        return 1;
    }

    std::string fecha_ejecucion = generarMarcaTiempo();
    fs::path carpeta_resultados =
        ruta_json.parent_path().parent_path()
        / "Results" / "ResultsCpp" / "Aceleracion";
    std::error_code error_directorio;
    fs::create_directories(carpeta_resultados, error_directorio);
    if (error_directorio) {
        std::cerr << "Error al crear la carpeta de resultados: "
                  << carpeta_resultados.string() << std::endl;
        return 1;
    }

    int presupuesto_b = 0;
    std::vector<Etapa> etapas;
    if (!cargarDatosJSON(ruta_json.string(), presupuesto_b, etapas)) {
        std::cerr << "Error: No se pudieron leer las etapas del JSON de entrada." << std::endl;
        return 1;
    }

    std::string ruta_csv =
        (carpeta_resultados / (
            "resultados_aceleracion_N"
            + std::to_string(etapas.size()) + "_" + fecha_ejecucion + ".csv"
        )).string();
    std::string ruta_csv_resumen =
        (carpeta_resultados / (
            "resumen_optimizacion_N"
            + std::to_string(etapas.size()) + "_" + fecha_ejecucion + ".csv"
        )).string();

    ResultadoPipeline resultado = optimizarAceleracionMochila(presupuesto_b, etapas);

    guardarResultadosCSV(resultado, ruta_csv);
    guardarResumenCSV(resultado, ruta_csv_resumen);

    const auto& res = resultado.resumen;
    std::cout << "Tiempo de programación dinámica: "
              << std::fixed << std::setprecision(9)
              << resultado.tiempo_programacion_dinamica << " segundos" << std::endl;
    std::cout << "\nRESUMEN DE LA OPTIMIZACIÓN" << std::endl;
    std::cout << "Duración inicial total: " << res.duracion_inicial_total << std::endl;
    std::cout << "Reducción lograda total: " << res.reduccion_lograda_total << std::endl;
    std::cout << "Duración final total: " << res.duracion_final_total << std::endl;
    std::cout << "Costo total: " << res.costo_acumulado_total << std::endl;

    std::cout << "Etapas seleccionadas: [";
    for (size_t i = 0; i < res.etapas_seleccionadas.size(); ++i) {
        std::cout << "'" << res.etapas_seleccionadas[i] << "'";
        if (i < res.etapas_seleccionadas.size() - 1) std::cout << ", ";
    }
    std::cout << "]" << std::endl;

    std::cout << std::fixed << std::setprecision(4);
    std::cout << "Eficiencia (red/costo): " << res.eficiencia_global << std::endl;
    std::cout << "Solución exportada: " << ruta_csv << std::endl;
    std::cout << "Resumen exportado: " << ruta_csv_resumen << std::endl;

    return 0;
}