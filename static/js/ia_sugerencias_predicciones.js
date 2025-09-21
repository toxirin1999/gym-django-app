// ia_sugerencias_predicciones.js

// =========================================================
// === 1. DEFINICIONES DE FUNCIONES DE LA IA (DEBEN IR PRIMERO) ===
//    Asegúrate de que todas tus funciones de lógica de IA y display
//    estén definidas aquí, FUERA del DOMContentLoaded listener.
// =========================================================

/**
 * Analiza el historial de entrenamientos y el entrenamiento actual para generar logros.
 * @param {Array} historialEntrenos - Historial de entrenamientos del usuario (parseado de JSON).
 * @param {Object} entrenoActual - Datos del entrenamiento actual (parseado de JSON).
 * @returns {Array<string>} - Lista de cadenas que describen los logros.
 */
function generarLogros(historialEntrenos, entrenoActual) {
    console.log("DEBUG: Ejecutando generarLogros", { historialEntrenos, entrenoActual });
    const logros = [];

    // Ejemplo de lógica de logros:
    if (entrenoActual && entrenoActual.series_por_ejercicio && entrenoActual.series_por_ejercicio.length > 0) {
        logros.push("¡Has completado tu entrenamiento de hoy!");
    }

    // Puedes añadir más lógica aquí, por ejemplo:
    // - Si se superó un peso máximo en un ejercicio
    // - Si se completó un número específico de entrenamientos en la semana/mes
    // - Si se entrenaron todos los grupos musculares planificados

    return logros;
}

/**
 * Genera sugerencias automáticas basadas en el historial de entrenamientos.
 * @param {Array} historialEntrenos - Historial de entrenamientos del usuario.
 * @param {Object} entrenoActual - Datos del entrenamiento actual.
 * @returns {Array<string>} - Lista de cadenas de sugerencias.
 */
function generarSugerenciasAutomaticas(historialEntrenos, entrenoActual) {
    console.log("DEBUG: Ejecutando generarSugerenciasAutomaticas", { historialEntrenos, entrenoActual });
    const sugerencias = [];

    // Ejemplo de lógica de sugerencias:
    if (historialEntrenos.length < 5) {
        sugerencias.push("¡Sigue así! Acumula más entrenamientos para obtener sugerencias más personalizadas.");
    } else {
        sugerencias.push("Considera variar tus ejercicios para un desarrollo muscular equilibrado.");
    }

    // Añade más lógica aquí:
    // - Sugerir aumento/disminución de peso/repeticiones basado en el progreso
    // - Recomendar días de descanso
    // - Sugerir nuevos ejercicios para grupos musculares menos trabajados

    return sugerencias;
}

/**
 * Genera predicciones de progreso futuro basadas en el historial.
 * @param {Array} historialEntrenos - Historial de entrenamientos del usuario.
 * @param {Object} entrenoActual - Datos del entrenamiento actual.
 * @returns {Array<string>} - Lista de cadenas de predicciones.
 */
function generarPrediccionesDeProgreso(historialEntrenos, entrenoActual) {
    console.log("DEBUG: Ejecutando generarPrediccionesDeProgreso", { historialEntrenos, entrenoActual });
    const predicciones = [];

    // Ejemplo de lógica de predicciones:
    if (historialEntrenos.length > 10) {
        predicciones.push("Basado en tu ritmo, podrías alcanzar un nuevo máximo personal en sentadilla en las próximas 4 semanas.");
    } else {
        predicciones.push("Continúa registrando tus entrenamientos para que la IA pueda predecir tu progreso.");
    }

    // Añade lógica más compleja:
    // - Predicción de 1RM
    // - Proyección de ganancia de peso/músculo si se mantiene el progreso
    // - Hitos esperados

    return predicciones;
}

/**
 * Muestra los logros en el contenedor HTML.
 * @param {Array<string>} logros - Los logros a mostrar.
 */
function displayLogros(logros) {
    console.log("DEBUG: Ejecutando displayLogros", { logros });
    const container = document.getElementById('logros-hoy-container');
    if (container) {
        if (logros && logros.length > 0) {
            container.innerHTML = '<ul class="list-unstyled">' + logros.map(logro => `<li><i class="fas fa-check-circle text-success me-2"></i>${logro}</li>`).join('') + '</ul>';
        } else {
            container.innerHTML = '<p class="text-muted">No hay logros destacados para hoy.</p>';
        }
    } else {
        console.warn("Contenedor 'logros-hoy-container' no encontrado.");
    }
}

/**
 * Muestra las sugerencias en el contenedor HTML.
 * @param {Array<string>} sugerencias - Las sugerencias a mostrar.
 */
function displaySugerencias(sugerencias) {
    console.log("DEBUG: Ejecutando displaySugerencias", { sugerencias });
    const container = document.getElementById('sugerencias-ia-container');
    if (container) {
        if (sugerencias && sugerencias.length > 0) {
            container.innerHTML = '<ul class="list-unstyled">' + sugerencias.map(sug => `<li><i class="fas fa-lightbulb text-warning me-2"></i>${sug}</li>`).join('') + '</ul>';
        } else {
            container.innerHTML = '<p class="text-muted">No hay sugerencias disponibles en este momento.</p>';
        }
    } else {
        console.warn("Contenedor 'sugerencias-ia-container' no encontrado.");
    }
}
// ia_sugerencias_predicciones.js

// ... (TUS DEFINICIONES DE generarLogros, displayLogros, generarSugerencias, displaySugerencias,
//        generarPredicciones, displayPredicciones, mostrarErrorCarga - deben ir aquí arriba) ...

/**
 * Muestra las medallas y logros en el contenedor HTML.
 * @param {Array<Object>} medallasLogros - Lista de objetos de medallas/logros.
 */
function displayMedallasLogros(medallasLogros) {
    console.log("DEBUG: Ejecutando displayMedallasLogros", { medallasLogros });
    const container = document.getElementById('medallas-logros-container');
    if (container) {
        if (medallasLogros && medallasLogros.length > 0) {
            let html = '<ul class="list-unstyled row">';
            medallasLogros.forEach(item => {
                html += `
                    <li class="col-6 col-md-4 col-lg-3 mb-3">
                        <div class="card h-100 text-center bg-light">
                            <div class="card-body">
                                <i class="${item.icono || 'fas fa-trophy'} fa-3x text-warning mb-2"></i>
                                <h5 class="card-title">${item.nombre}</h5>
                                <p class="card-text text-muted">${item.descripcion}</p>
                            </div>
                        </div>
                    </li>
                `;
            });
            html += '</ul>';
            container.innerHTML = html;
        } else {
            container.innerHTML = '<p class="text-muted">Aún no has obtenido ninguna medalla o logro. ¡Sigue entrenando!</p>';
        }
    } else {
        console.warn("Contenedor 'medallas-logros-container' no encontrado.");
    }
}

/**
 * Muestra las tablas de clasificación en el contenedor HTML.
 * @param {Array<Object>} leaderboardData - Lista de tablas de clasificación.
 */
function displayLeaderboard(leaderboardData) {
    console.log("DEBUG: Ejecutando displayLeaderboard", { leaderboardData });
    const container = document.getElementById('leaderboard-container');
    if (container) {
        if (leaderboardData && leaderboardData.length > 0) {
            let html = '<div class="row">';
            leaderboardData.forEach(board => {
                html += `
                    <div class="col-md-6 mb-4">
                        <div class="card h-100">
                            <div class="card-header bg-secondary text-white">${board.titulo}</div>
                            <ul class="list-group list-group-flush">
                                ${board.items.map((item, index) => `
                                    <li class="list-group-item d-flex justify-content-between align-items-center">
                                        <span class="badge bg-primary rounded-pill me-2">${index + 1}</span>
                                        ${item.nombre}
                                        <span class="badge bg-secondary rounded-pill">${item.valor}</span>
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            container.innerHTML = html;
        } else {
            container.innerHTML = '<p class="text-muted">Las tablas de clasificación no están disponibles en este momento.</p>';
        }
    } else {
        console.warn("Contenedor 'leaderboard-container' no encontrado.");
    }
}
/**
 * Muestra las predicciones en el contenedor HTML.
 * @param {Array<string>} predicciones - Las predicciones a mostrar.
 */
function displayPredicciones(predicciones) {
    console.log("DEBUG: Ejecutando displayPredicciones", { predicciones });
    const container = document.getElementById('predicciones-progreso-container');
    if (container) {
        if (predicciones && predicciones.length > 0) {
            container.innerHTML = '<ul class="list-unstyled">' + predicciones.map(pred => `<li><i class="fas fa-chart-line text-info me-2"></i>${pred}</li>`).join('') + '</ul>';
        } else {
            container.innerHTML = '<p class="text-muted">No hay predicciones de progreso disponibles.</p>';
        }
    } else {
        console.warn("Contenedor 'predicciones-progreso-container' no encontrado.");
    }
}

/**
 * Muestra un mensaje de error en los contenedores de la IA si la carga falla.
 */
function mostrarErrorCarga() {
    console.error("DEBUG: Ejecutando mostrarErrorCarga - mostrando mensaje de fallo.");
    const errorMessage = '<p class="text-danger">No se pudieron cargar los datos. Por favor, recarga la página o inténtalo más tarde.</p>';

    const logrosContainer = document.getElementById('logros-hoy-container');
    if (logrosContainer) {
        logrosContainer.innerHTML = errorMessage;
    }
    const sugerenciasContainer = document.getElementById('sugerencias-ia-container');
    if (sugerenciasContainer) {
        sugerenciasContainer.innerHTML = errorMessage;
    }
    const prediccionesContainer = document.getElementById('predicciones-progreso-container');
    if (prediccionesContainer) {
        prediccionesContainer.innerHTML = errorMessage;
    }
}

// =========================================================
// === INICIALIZACIÓN DEL MÓDULO (UNICO DOMContentLoaded) ===
// =========================================================
document.addEventListener('DOMContentLoaded', function() {
    console.log("Inicializando módulo de IA para sugerencias y predicciones (desde ia_sugerencias_predicciones.js)");

    const historialJSON = document.getElementById('historial-data')?.value;
    const entrenoActualJSON = document.getElementById('entreno-actual-data')?.value;

    // --- NUEVOS INPUTS para Gamificación ---
    const medallasLogrosJSON = document.getElementById('medallas-logros-data')?.value; // Asegúrate de añadir el input en HTML
    const leaderboardJSON = document.getElementById('leaderboard-data')?.value;       // Asegúrate de añadir el input en HTML

    console.log("--- DEBUGGING IA DATA (desde ia_sugerencias_predicciones.js) ---");
    console.log("Valor RAW de historial-data:", historialJSON);
    console.log("Valor RAW de entreno-actual-data:", entrenoActualJSON);
    console.log("Valor RAW de medallas-logros-data:", medallasLogrosJSON); // Nuevo log
    console.log("Valor RAW de leaderboard-data:", leaderboardJSON);       // Nuevo log
    console.log("-------------------------------------------------");

    try {
        const historial = JSON.parse(historialJSON || '[]');
        const entrenoActual = JSON.parse(entrenoActualJSON || '{}');

        // --- Parsear los nuevos JSON de Gamificación ---
        const medallasLogros = JSON.parse(medallasLogrosJSON || '[]');
        const leaderboardData = JSON.parse(leaderboardJSON || '[]');

        console.log("Datos cargados para IA (parseados desde ia_sugerencias_predicciones.js):", {
            historial: historial,
            entrenoActual: entrenoActual,
            medallasLogros: medallasLogros,   // Incluir en el log
            leaderboardData: leaderboardData, // Incluir en el log
        });

        if (historial.length === 0) {
            console.warn("Historial de entrenos está vacío (desde ia_sugerencias_predicciones.js).");
        }
        if (Object.keys(entrenoActual).length === 0) {
            console.warn("Entreno actual está vacío (desde ia_sugerencias_predicciones.js).");
        }
        if (medallasLogros.length === 0) { // Nueva advertencia
            console.warn("Datos de medallas/logros están vacíos.");
        }
        if (leaderboardData.length === 0) { // Nueva advertencia
            console.warn("Datos de leaderboard están vacíos.");
        }


        // Llama a las funciones para generar y mostrar los resultados de la IA original
        const logros = generarLogros(historial, entrenoActual);
        console.log("Logros generados:", logros);
        displayLogros(logros);

        const sugerencias = generarSugerenciasAutomaticas(historial, entrenoActual);
        console.log("Sugerencias generadas:", sugerencias);
        displaySugerencias(sugerencias);

        const predicciones = generarPrediccionesDeProgreso(historial, entrenoActual);
        console.log("Predicciones generadas:", predicciones);
        displayPredicciones(predicciones);

        // --- Llama a las nuevas funciones para mostrar Gamificación ---
        displayMedallasLogros(medallasLogros); // Mostrar las medallas y logros
        displayLeaderboard(leaderboardData);   // Mostrar las tablas de clasificación


    } catch (error) {
        console.error("Error al parsear o procesar datos JSON para IA o Gamificación (desde ia_sugerencias_predicciones.js):", error);
        mostrarErrorCarga(); // Esta función mostrará el mensaje de error en todos los contenedores
    }
});