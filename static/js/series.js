/**
 * Configura los event listeners para las series
 */
function setupSeriesHandlers() {
    document.querySelectorAll('.fitness-ring').forEach(ring => {
        ring.addEventListener('click', () => disminuirReps(ring));
    });
}

/**
 * Maneja la disminución de repeticiones
 */
function disminuirReps(ring) {
    const span = ring.querySelector('.rep-counter');
    const inputReps = ring.querySelector('input[type="hidden"]');
    const original = parseInt(ring.dataset.original);
    let valor = parseInt(span.textContent) || original;

    // Primera interacción: marcar como seleccionado
    if (!ring.classList.contains('selected')) {
        ring.classList.add('selected');
        inputReps.value = valor;
        updateStats();
        return;
    }

    // Disminuir repeticiones
    valor = valor > 0 ? valor - 1 : original;
    span.textContent = valor;
    inputReps.value = valor;

    // Completar si vuelve al valor original
    if (valor === original) {
        ring.classList.remove('selected');
        ring.classList.add('completed');
    }

    // Actualizar input hidden
    const completadoInput = ring.closest('.serie-item').querySelector('input[name$="_completado"]');
    if (completadoInput) completadoInput.value = (valor === original) ? "1" : "0";

    // Reiniciar descanso y estadísticas
    iniciarCronometroDescanso();
    updateStats();
}

/**
 * Agrega una nueva serie
 */
function agregarSerie(button, ejercicioId) {
    const lista = button.closest('.fitness-card-body').querySelector('.series-list');
    const count = lista.querySelectorAll('.serie-item').length + 1;
    const repsPrevias = button.dataset.reps || '12';
    const pesoPrevio = button.dataset.peso || '0';
    const originalReps = button.dataset.original || repsPrevias;

    const nuevaSerie = document.createElement('div');
    nuevaSerie.className = 'serie-item mb-3 new-serie';
    nuevaSerie.dataset.numero = count;

    nuevaSerie.innerHTML = `
        <div class="fitness-ring me-3" data-original="${originalReps}">
            <span class="rep-counter">${repsPrevias}</span>
            <input type="hidden" name="${ejercicioId}_reps_${count}" value="${repsPrevias}">
        </div>
        <div class="serie-info">
            <div class="serie-title">Serie ${count}</div>
            <input type="hidden" name="${ejercicioId}_peso_${count}" value="${pesoPrevio}">
            <input type="hidden" name="${ejercicioId}_completado_${count}" value="0">
            <div class="serie-details">Nueva serie</div>
        </div>
    `;

    lista.appendChild(nuevaSerie);
    nuevaSerie.querySelector('.fitness-ring').addEventListener('click', function() {
        disminuirReps(this);
    });

    // Animación y actualizaciones
    setTimeout(() => nuevaSerie.classList.remove('new-serie'), 300);
    iniciarCronometroDescanso();
    updateStats();
}

/**
 * Actualiza las estadísticas del entrenamiento
 */
function updateStats() {
    const totalSeries = document.querySelectorAll('.serie-item').length;
    const completedSeries = document.querySelectorAll('.fitness-ring.completed').length;
    const statsElement = document.getElementById('workout-stats') || document.createElement('div');

    statsElement.innerHTML = `
        <div class="d-flex gap-2 mt-3">
            <span class="fitness-badge success">
                <i class="bi bi-check-circle"></i> ${completedSeries}/${totalSeries} series
            </span>
        </div>
    `;
}

// Exportar funciones para uso global
window.setupSeriesHandlers = setupSeriesHandlers;
window.disminuirReps = disminuirReps;
window.agregarSerie = agregarSerie;
window.updateStats = updateStats;