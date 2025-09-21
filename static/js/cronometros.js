/**
 * Cronómetros para la página de entrenamiento
 * - Cronómetro total: mide la duración total del entrenamiento
 * - Cronómetro de descanso: se reinicia cada vez que se registran repeticiones
 */

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
    
    // Guardar tiempo de inicio
    tiempoTotalInicio = new Date();
    
    // Actualizar el cronómetro cada segundo
    tiempoTotalInterval = setInterval(actualizarCronometroTotal, 1000);
    
    // Actualización inicial
    actualizarCronometroTotal();
}

/**
 * Actualiza la visualización del cronómetro total
 */
function actualizarCronometroTotal() {
    const ahora = new Date();
    const diferencia = ahora - tiempoTotalInicio;
    
    // Convertir a formato hh:mm:ss
    const horas = Math.floor(diferencia / 3600000);
    const minutos = Math.floor((diferencia % 3600000) / 60000);
    const segundos = Math.floor((diferencia % 60000) / 1000);
    
    // Formatear con ceros a la izquierda
    const horasStr = horas.toString().padStart(2, '0');
    const minutosStr = minutos.toString().padStart(2, '0');
    const segundosStr = segundos.toString().padStart(2, '0');
    
    // Actualizar el elemento HTML
    const cronometroTotal = document.getElementById('cronometro-total');
    if (cronometroTotal) {
        cronometroTotal.textContent = `${horasStr}:${minutosStr}:${segundosStr}`;
    }
}

/**
 * Detiene el cronómetro total
 */
function detenerCronometroTotal() {
    if (tiempoTotalInterval) {
        clearInterval(tiempoTotalInterval);
        tiempoTotalInterval = null;
    }
}

/**
 * Inicia o reinicia el cronómetro de descanso
 */
function iniciarCronometroDescanso() {
    // Detener el intervalo anterior si existe
    if (tiempoDescansoInterval) {
        clearInterval(tiempoDescansoInterval);
    }
    
    // Guardar tiempo de inicio
    tiempoDescansoInicio = new Date();
    
    // Actualizar el cronómetro cada segundo
    tiempoDescansoInterval = setInterval(actualizarCronometroDescanso, 1000);
    
    // Actualización inicial
    actualizarCronometroDescanso();
}

/**
 * Actualiza la visualización del cronómetro de descanso
 */
function actualizarCronometroDescanso() {
    const ahora = new Date();
    const diferencia = ahora - tiempoDescansoInicio;
    
    // Convertir a formato mm:ss
    const minutos = Math.floor(diferencia / 60000);
    const segundos = Math.floor((diferencia % 60000) / 1000);
    
    // Formatear con ceros a la izquierda
    const minutosStr = minutos.toString().padStart(2, '0');
    const segundosStr = segundos.toString().padStart(2, '0');
    
    // Actualizar el elemento HTML
    const cronometroDescanso = document.getElementById('cronometro-descanso');
    if (cronometroDescanso) {
        cronometroDescanso.textContent = `${minutosStr}:${segundosStr}`;
    }
}

/**
 * Configura los eventos para reiniciar el cronómetro de descanso
 * cuando se ingresan repeticiones
 */
function configurarEventosReinicioDescanso() {
    // Seleccionar todos los campos de repeticiones
    const camposRepeticiones = document.querySelectorAll('input[id$="_reps"]');
    
    // Añadir evento para reiniciar el cronómetro al cambiar el valor
    camposRepeticiones.forEach(campo => {
        campo.addEventListener('change', iniciarCronometroDescanso);
    });
}

/**
 * Inicializa los cronómetros cuando se carga la página
 */
document.addEventListener('DOMContentLoaded', function() {
    // Iniciar cronómetro total
    iniciarCronometroTotal();
    
    // Iniciar cronómetro de descanso
    iniciarCronometroDescanso();
    
    // Configurar eventos para reiniciar el cronómetro de descanso
    configurarEventosReinicioDescanso();
    
    // Añadir evento al botón de finalizar entrenamiento
    const botonFinalizar = document.getElementById('btn-finalizar-entreno');
    if (botonFinalizar) {
        botonFinalizar.addEventListener('click', function() {
            detenerCronometroTotal();
        });
    }
});
