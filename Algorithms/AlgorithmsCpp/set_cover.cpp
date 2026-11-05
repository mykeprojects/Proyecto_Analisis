#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <unordered_set>
#include <set>
#include <sstream>
#include <algorithm>
#include <iomanip>
#include <cmath>
#include <chrono>
#include <ctime>
#include <filesystem>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

// Estructura para almacenar cada etapa/interacción candidata
struct Interaccion {
    std::string id;
    std::unordered_set<std::string> riesgos_cubiertos;
};

// Estructura para el resultado de la selección voraz
struct SeleccionPaso {
    std::string id_interaccion;
    std::vector<std::string> nuevos_riesgos;
};

// 1. Lector de JSON simplificado sin dependencias externas
bool cargarJSONAuditoria(const std::string& ruta, std::vector<std::string>& categorias_totales, std::vector<Interaccion>& interacciones) {
    std::ifstream file(ruta);
    if (!file.is_open()) return false;

    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string content = buffer.str();
    file.close();

    // Extraer categorias_riesgo (IDs "R01", "R02", ...)
    size_t pos_cat = content.find("\"categorias_riesgo\"");
    size_t pos_etapas = content.find("\"etapas\"");
    if (pos_cat == std::string::npos || pos_etapas == std::string::npos) return false;

    std::string bloque_cat = content.substr(pos_cat, pos_etapas - pos_cat);
    size_t p = 0;
    while ((p = bloque_cat.find("\"id\"", p)) != std::string::npos) {
        size_t start_q = bloque_cat.find("\"", bloque_cat.find(":", p));
        size_t end_q = bloque_cat.find("\"", start_q + 1);
        std::string r_id = bloque_cat.substr(start_q + 1, end_q - start_q - 1);
        if (r_id.front() == 'R') {
            categorias_totales.push_back(r_id);
        }
        p = end_q + 1;
    }

    // Extraer etapas
    p = pos_etapas;
    while ((p = content.find("\"duracion_normal\"", p)) != std::string::npos) {
        size_t start_obj = content.rfind("{", p);
        size_t end_obj = content.find("}", p);
        std::string block = content.substr(start_obj, end_obj - start_obj + 1);

        // Extraer id de etapa
        size_t id_p = block.find("\"id\"");
        size_t sq = block.find("\"", block.find(":", id_p));
        size_t eq = block.find("\"", sq + 1);
        std::string e_id = block.substr(sq + 1, eq - sq - 1);

        // Extraer riesgos_cubiertos_auditoria_completa
        std::unordered_set<std::string> riesgos;
        size_t r_list_pos = block.find("\"riesgos_cubiertos_auditoria_completa\"");
        if (r_list_pos != std::string::npos) {
            size_t end_list = block.find("]", r_list_pos);
            std::string r_block = block.substr(r_list_pos, end_list - r_list_pos);
            size_t rp = 0;
            while ((rp = r_block.find("\"R", rp)) != std::string::npos) {
                size_t req = r_block.find("\"", rp + 1);
                riesgos.insert(r_block.substr(rp + 1, req - rp - 1));
                rp = req + 1;
            }
        }

        interacciones.push_back({e_id, riesgos});
        p = end_obj + 1;
    }

    return !interacciones.empty();
}

// 2. Verificación de Factibilidad O(n * r)
bool verificarFactibilidad(const std::vector<Interaccion>& interacciones, const std::unordered_set<std::string>& universo_requerido) {
    std::unordered_set<std::string> union_cubierta;
    for (const auto& item : interacciones) {
        for (const auto& r : item.riesgos_cubiertos) {
            union_cubierta.insert(r);
        }
    }
    for (const auto& req : universo_requerido) {
        if (union_cubierta.find(req) == union_cubierta.end()) {
            return false;
        }
    }
    return true;
}

// 3. Algoritmo Voraz Set Cover O(n * r * min(n, r))
std::vector<SeleccionPaso> ejecutarSetCoverVoraz(const std::vector<Interaccion>& interacciones, std::unordered_set<std::string> pendientes) {
    std::vector<SeleccionPaso> seleccionadas;
    std::vector<bool> usadas(interacciones.size(), false);

    while (!pendientes.empty()) {
        int mejor_idx = -1;
        std::vector<std::string> mejor_nuevos;

        for (size_t i = 0; i < interacciones.size(); ++i) {
            if (usadas[i]) continue;
            std::vector<std::string> nuevos;
            for (const auto& r : interacciones[i].riesgos_cubiertos) {
                if (pendientes.count(r)) {
                    nuevos.push_back(r);
                }
            }
            if (nuevos.size() > mejor_nuevos.size()) {
                mejor_nuevos = nuevos;
                mejor_idx = static_cast<int>(i);
            }
        }

        if (mejor_idx == -1 || mejor_nuevos.empty()) break;

        usadas[mejor_idx] = true;
        seleccionadas.push_back({interacciones[mejor_idx].id, mejor_nuevos});
        for (const auto& r : mejor_nuevos) {
            pendientes.erase(r);
        }
    }

    return seleccionadas;
}

// 4. Persistencia en CSV
void guardarCSV(
    const std::vector<SeleccionPaso>& pasos,
    const std::string& ruta
) {
    std::ofstream csv(ruta);
    csv << "orden_seleccion,id_interaccion,nuevos_riesgos_cubiertos,"
           "cantidad_nuevos_riesgos\n";
    for (size_t i = 0; i < pasos.size(); ++i) {
        csv << (i + 1) << "," << pasos[i].id_interaccion << ",\"";
        for (size_t j = 0; j < pasos[i].nuevos_riesgos.size(); ++j) {
            csv << pasos[i].nuevos_riesgos[j] << (j + 1 < pasos[i].nuevos_riesgos.size() ? ";" : "");
        }
        csv << "\"," << pasos[i].nuevos_riesgos.size() << "\n";
    }
    csv.close();
}

int main(int argc, char* argv[]) {
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

    std::vector<std::string> categorias_raw;
    std::vector<Interaccion> interacciones;

    if (!cargarJSONAuditoria(ruta_json.string(), categorias_raw, interacciones)) {
        std::cerr << "Error al cargar el archivo JSON." << std::endl;
        return 1;
    }

    std::unordered_set<std::string> universo_req(categorias_raw.begin(), categorias_raw.end());
    size_t n = interacciones.size();
    size_t r = universo_req.size();

    // Verificación O(n * r)
    bool factible = verificarFactibilidad(interacciones, universo_req);
    std::cout << "2. Verificación de Factibilidad O(n·r): " << (factible ? "FACTIBLE" : "INFACTIBLE") << std::endl;

    if (!factible) {
        std::cerr << "La instancia no satisface la cobertura total de riesgos." << std::endl;
        return 1;
    }

    // Ejecución Voraz
    auto inicio_setcover = std::chrono::high_resolution_clock::now();
    std::vector<SeleccionPaso> resultado = ejecutarSetCoverVoraz(interacciones, universo_req);
    auto fin_setcover = std::chrono::high_resolution_clock::now();
    double tiempo_setcover = std::chrono::duration<double>(
        fin_setcover - inicio_setcover).count();

    // Calcular cotas armónicas H(d) y H(r)
    size_t d_max = 0;
    for (const auto& item : interacciones) {
        d_max = std::max(d_max, item.riesgos_cubiertos.size());
    }

    double H_d = 0.0, H_r = 0.0;
    for (size_t i = 1; i <= d_max; ++i) H_d += 1.0 / i;
    for (size_t i = 1; i <= r; ++i) H_r += 1.0 / i;

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
    std::ostringstream id_stream;
    id_stream << std::put_time(&tiempo_local, "%Y%m%d_%H%M%S")
              << "_" << std::setw(6) << std::setfill('0') << micros;
    std::string fecha_ejecucion = id_stream.str();
    fs::path carpeta_resultados =
        ruta_json.parent_path().parent_path() / "Results" / "ResultsCpp" / "SetCover";
    std::error_code error_directorio;
    fs::create_directories(carpeta_resultados, error_directorio);
    if (error_directorio) {
        std::cerr << "Error al crear la carpeta de resultados: "
                  << carpeta_resultados.string() << std::endl;
        return 1;
    }
    fs::path ruta_csv = carpeta_resultados /
        ("resultados_setcover_N" + std::to_string(n) + "_" + fecha_ejecucion + ".csv");
    guardarCSV(resultado, ruta_csv.string());

    // Impresión en Consola
    std::cout << "\n=================================================================" << std::endl;
    std::cout << "      RESULTADOS DE COBERTURA MÍNIMA DE AUDITORÍA (SET COVER)" << std::endl;
    std::cout << "=================================================================" << std::endl;
    std::cout << "• Interacciones evaluadas (n)   : " << n << std::endl;
    std::cout << "• Categorías de riesgo (r)      : " << r << std::endl;
    std::cout << "• Máximo cobertura por nodo (d) : " << d_max << std::endl;
    std::cout << "• Tamaño Cobertura Voraz        : " << resultado.size() << " interacciones -> [";
    for (size_t i = 0; i < resultado.size(); ++i) {
        std::cout << "'" << resultado[i].id_interaccion << "'" << (i + 1 < resultado.size() ? ", " : "");
    }
    std::cout << "]" << std::endl;

    std::cout << std::fixed << std::setprecision(4);
    std::cout << "-----------------------------------------------------------------" << std::endl;
    std::cout << "VERIFICACIÓN TEOREMA 4.3.1 (COTA DE CHVÁTAL / JOHNSON):" << std::endl;
    std::cout << "  - Cota armónica H(d)          = " << H_d << std::endl;
    std::cout << "  - Cota armónica global H(r)   = " << H_r << std::endl;
    std::cout << "• Persistencia guardada en CSV  : " << ruta_csv << std::endl;
    std::cout << "• Tiempo de ejecución Voraz    : "
              << std::fixed << std::setprecision(3)
              << tiempo_setcover * 1000 << " ms" << std::endl;
    std::cout << "=================================================================" << std::endl;

    return 0;
}