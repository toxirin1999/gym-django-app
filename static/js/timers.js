// Variables globales para los cronómetros
let tiempoTotalInicio = null;
let tiempoTotalInterval = null;
let tiempoDescansoInicio = null;
let tiempoDescansoInterval = null;

/**
 * Inicia el cronómetro total del entrenamiento
 */
function iniciarCronometroTotal() {
    // Si ya está iniciado, no hacer nada
    if (tiempoTotalInicio !== null) return;

    // Intentar cargar desde localStorage
    const savedTime = localStorage.getItem('workoutStartTime');
    tiempoTotalInicio = savedTime ? new Date(savedTime) : new Date();

    // Guardar tiempo si es nuevo
    if (!savedTime) {
        localStorage.setItem('workoutStartTime', tiempoTotalInicio.toISOString());
    }

    // Actualizar cada segundo
    tiempoTotalInterval = setInterval(actualizarCronometroTotal, 1000);
    actualizarCronometroTotal();
}

/**
 * Actualiza el cronómetro total
 */
function actualizarCronometroTotal() {
    const ahora = new Date();
    const diferencia = ahora - tiempoTotalInicio;

    // Formatear a hh:mm:ss
    const horas = Math.floor(diferencia / 3600000).toString().padStart(2, '0');
    const minutos = Math.floor((diferencia % 3600000) / 60000).toString().padStart(2, '0');
    const segundos = Math.floor((diferencia % 60000) / 1000).toString().padStart(2, '0');

    // Actualizar UI
    const elemento = document.getElementById('cronometro-total');
    if (elemento) elemento.textContent = `${horas}:${minutos}:${segundos}`;
}

/**
 * Detiene el cronómetro total
 */
function detenerCronometroTotal() {
    clearInterval(tiempoTotalInterval);
    tiempoTotalInterval = null;
    localStorage.removeItem('workoutStartTime');
}

/**
 * Inicia/reinicia el cronómetro de descanso
 */
function iniciarCronometroDescanso() {
    // Detener si ya existe
    if (tiempoDescansoInterval) clearInterval(tiempoDescansoInterval);

    // Reproducir sonido
    const sound = document.getElementById('restSound');
    if (sound) sound.play().catch(e => console.log("No se pudo reproducir sonido:", e));

    // Configurar nuevo temporizador
    tiempoDescansoInicio = new Date();
    tiempoDescansoInterval = setInterval(actualizarCronometroDescanso, 1000);
    actualizarCronometroDescanso();

    // Animación
    const elemento = document.getElementById('cronometro-descanso');
    if (elemento) {
        elemento.classList.add('pulse-animation');
        setTimeout(() => elemento.classList.remove('pulse-animation'), 500);
    }
}

/**
 * Actualiza el cronómetro de descanso
 */
function actualizarCronometroDescanso() {
    const ahora = new Date();
    const diferencia = ahora - tiempoDescansoInicio;

    // Formatear a mm:ss
    const minutos = Math.floor(diferencia / 60000).toString().padStart(2, '0');
    const segundos = Math.floor((diferencia % 60000) / 1000).toString().padStart(2, '0');

    // Actualizar UI
    const elemento = document.getElementById('cronometro-descanso');
    if (elemento) elemento.textContent = `${minutos}:${segundos}`;
}

// Exportar funciones para uso global
window.iniciarCronometroTotal = iniciarCronometroTotal;
window.detenerCronometroTotal = detenerCronometroTotal;
window.iniciarCronometroDescanso = iniciarCronometroDescanso;