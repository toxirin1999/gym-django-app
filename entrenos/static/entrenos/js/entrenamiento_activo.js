// =======================================================
// FUNCIONES PARA SECCIONES COLAPSABLES
// =======================================================
function toggleSection(sectionId) {
    const content = document.getElementById(sectionId + '-content');
    const icon = document.getElementById(sectionId + '-icon');
    const isCollapsed = content.style.maxHeight === '0px' || content.style.maxHeight === '';

    if (isCollapsed) {
        // Expandir
        content.style.maxHeight = content.scrollHeight + 'px';
        icon.style.transform = 'rotate(180deg)';
        localStorage.setItem('section_' + sectionId, 'expanded');
    } else {
        // Colapsar
        content.style.maxHeight = '0px';
        icon.style.transform = 'rotate(0deg)';
        localStorage.setItem('section_' + sectionId, 'collapsed');
    }
}

function initCollapsibleSections() {
    const sections = ['guia-rpe', 'mision', 'gamificacion'];

    sections.forEach(sectionId => {
        const content = document.getElementById(sectionId + '-content');
        const icon = document.getElementById(sectionId + '-icon');

        if (content && icon) {
            const savedState = localStorage.getItem('section_' + sectionId);

            // Por defecto, colapsar las secciones informativas
            if (savedState === 'expanded') {
                content.style.maxHeight = content.scrollHeight + 'px';
                icon.style.transform = 'rotate(180deg)';
            } else {
                // Colapsado por defecto
                content.style.maxHeight = '0px';
                icon.style.transform = 'rotate(0deg)';
            }
        }
    });
}

// Inicializar al cargar la página
document.addEventListener('DOMContentLoaded', initCollapsibleSections);

// =======================================================
// FUNCIÓN PARA OBTENER ICONO DE GRUPO MUSCULAR
// =======================================================
function getIconoGrupo(grupo) {
    const iconos = {
        'pecho': 'fa-chess-board',
        'espalda': 'fa-expand-alt',
        'piernas': 'fa-shoe-prints',
        'cuadriceps': 'fa-shoe-prints',
        'cuadríc': 'fa-shoe-prints',
        'isquiotibiales': 'fa-shoe-prints',
        'isquios': 'fa-shoe-prints',
        'gluteos': 'fa-shoe-prints',
        'glúteos': 'fa-shoe-prints',
        'hombros': 'fa-hands',
        'deltoides': 'fa-hands',
        'biceps': 'fa-hand-rock',
        'bíceps': 'fa-hand-rock',
        'triceps': 'fa-hand-rock',
        'tríceps': 'fa-hand-rock',
        'brazos': 'fa-hand-rock',
        'core': 'fa-circle',
        'abdominales': 'fa-circle',
        'general': 'fa-dumbbell'
    };
    return iconos[grupo.toLowerCase()] || 'fa-dumbbell';
}

// =======================================================
// FUNCIONES PARA BARRA DE PROGRESO DEL ENTRENAMIENTO
// =======================================================
function updateWorkoutProgress() {
    // Obtener todos los checkboxes de series efectivas (no aproximaciones)
    const allCheckboxes = document.querySelectorAll('.serie-row:not(.serie-aproximacion) input[type="checkbox"][name]');
    const checkedCheckboxes = document.querySelectorAll('.serie-row:not(.serie-aproximacion) input[type="checkbox"][name]:checked');

    const totalSeries = allCheckboxes.length;
    const completedSeries = checkedCheckboxes.length;

    // Agrupar series por ejercicio usando el prefijo del nombre (ej: "ejercicio_1_completado_1" -> "ejercicio_1")
    const ejerciciosMap = {};

    allCheckboxes.forEach(checkbox => {
        const name = checkbox.name;
        if (name) {
            // Extraer el identificador del ejercicio (todo antes de "_completado_")
            const match = name.match(/(.+)_completado_\d+/);
            if (match) {
                const ejercicioId = match[1];
                if (!ejerciciosMap[ejercicioId]) {
                    ejerciciosMap[ejercicioId] = {total: 0, completed: 0, header: null};
                }
                ejerciciosMap[ejercicioId].total++;
                if (checkbox.checked) {
                    ejerciciosMap[ejercicioId].completed++;
                }
            }
        }
    });

    // Contar ejercicios totales y completados
    const ejercicioIds = Object.keys(ejerciciosMap);
    const totalEjercicios = ejercicioIds.length;
    let ejerciciosCompletados = 0;

    ejercicioIds.forEach(id => {
        const ej = ejerciciosMap[id];
        if (ej.total > 0 && ej.total === ej.completed) {
            ejerciciosCompletados++;
        }
    });

    // Actualizar barra de progreso
    const progressBar = document.getElementById('workout-progress-bar');
    const progressText = document.getElementById('progress-text');
    const seriesText = document.getElementById('series-completed-text');

    if (progressBar && progressText && seriesText) {
        // El porcentaje se basa en las series completadas (más granular que ejercicios)
        const percentageSeries = totalSeries > 0 ? (completedSeries / totalSeries) * 100 : 0;
        const percentageEjercicios = totalEjercicios > 0 ? (ejerciciosCompletados / totalEjercicios) * 100 : 0;

        progressBar.style.width = percentageSeries + '%';
        progressText.textContent = ejerciciosCompletados + ' / ' + totalEjercicios + ' ejercicios';
        seriesText.textContent = completedSeries + ' / ' + totalSeries + ' series completadas';

        // Cambiar color del porcentaje según progreso (siempre dorado)
        if (percentageText) {
            percentageText.textContent = Math.round(percentageSeries) + '%';
            percentageText.style.color = percentageSeries === 100 ? '#4ade80' : '#d4a847';
        }

        // Cambiar color según progreso
        if (percentageSeries === 100) {
            progressBar.style.background = 'linear-gradient(90deg, #a07820, #d4a847)';
        } else if (percentageSeries >= 50) {
            progressBar.style.background = 'linear-gradient(90deg, #a07820, #d4a847)';
        } else {
            progressBar.style.background = 'linear-gradient(90deg, #6a5010, #a07820)';
        }

        // Actualizar tiempo estimado restante (aprox 2 min por serie)
        const seriesRestantes = totalSeries - completedSeries;
        const tiempoEstimado = seriesRestantes * 2; // 2 minutos por serie
        const tiempoText = document.getElementById('tiempo-estimado-text');
        if (tiempoText) {
            if (seriesRestantes === 0) {
                tiempoText.textContent = 'Tiempo estimado: ¡Completado!';
            } else {
                tiempoText.textContent = 'Tiempo estimado: ~' + tiempoEstimado + ' min';
            }
        }
    }
}

// Inicializar listeners para checkboxes
document.addEventListener('DOMContentLoaded', function () {
    const checkboxes = document.querySelectorAll('.serie-row input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            updateWorkoutProgress();
            handleSerieCompletion(this);
        });
    });
    // Actualizar progreso inicial
    updateWorkoutProgress();
    // Restaurar estado de series completadas
    checkboxes.forEach(checkbox => {
        if (checkbox.checked) {
            const row = checkbox.closest('.serie-row');
            if (row) row.classList.add('serie-completada');
        }
    });
});

// =======================================================
// FUNCIONES PARA FEEDBACK VISUAL AL COMPLETAR SERIES
// =======================================================
function handleSerieCompletion(checkbox) {
    const row = checkbox.closest('.serie-row');
    if (!row) return;

    if (checkbox.checked) {
        row.classList.add('serie-completada');

        // Efecto de celebración pequeño
        createMiniCelebration(row);

        // Vibrar si está disponible (móvil)
        if (navigator.vibrate) {
            navigator.vibrate(50);
        }
        // --- Al completar la 1ª serie REAL de este ejercicio: colapsar aproximaciones y marcar “calentamiento listo”
        // Determinar si es una serie real (no aproximación)
        const serieLabel = row.querySelector('.serie-cell strong');
        const esSerieReal = serieLabel && serieLabel.textContent.includes('Serie');
        if (esSerieReal) {
            const exerciseBlock = row.closest('.exercise-block') || row.closest('.exercise-card') || row.closest('.card') || row.parentElement;

            // Encuentra el bloque de aproximaciones de este ejercicio (si existe)
            const aproxBlock = exerciseBlock ? exerciseBlock.querySelector('[data-aprox]') : null;
            if (aproxBlock) {
                const toggle = aproxBlock.querySelector('[data-aprox-toggle]');
                const content = aproxBlock.querySelector('[data-aprox-content]');
                const badge = aproxBlock.querySelector('[data-warmup-status]');

                // Mostrar badge
                if (badge) badge.hidden = false;

                // Colapsar (cerrar) si está abierto
                if (toggle && content) {
                    toggle.setAttribute('aria-expanded', 'false');
                    content.hidden = true;
                }
                // Focus automático a la siguiente serie real
                focusSiguienteSerie(row);

            }
        }

        // --- AUTO DESCANSO (solo series reales, no aproximaciones) ---

        if (esSerieReal) {
            // Buscar el rest-timer-box de ESTE ejercicio (está antes de las series)
            let prev = row;
            let restBox = null;

            while (prev && (prev = prev.previousElementSibling)) {
                if (prev.classList && prev.classList.contains('rest-timer-box')) {
                    restBox = prev;
                    break;
                }
            }

            if (restBox) {
                const btn = restBox.querySelector('.rest-timer-btn');
                const minutes = parseInt(restBox.dataset.restSeconds, 10) || 1;
                if (btn) startRestTimer(btn, minutes);
            }
        }

    } else {
        row.classList.remove('serie-completada');
    }
}

function createMiniCelebration(element) {
    // Crear partículas de celebración
    const colors = ['#d4a847', '#f0d080', '#c0392b', '#a07820'];
    const rect = element.getBoundingClientRect();

    for (let i = 0; i < 8; i++) {
        const particle = document.createElement('div');
        particle.style.cssText = `
                position: fixed;
                width: 8px;
                height: 8px;
                background: ${colors[Math.floor(Math.random() * colors.length)]};
                border-radius: 50%;
                pointer-events: none;
                z-index: 9999;
                left: ${rect.right - 30}px;
                top: ${rect.top + rect.height / 2}px;
            `;
        document.body.appendChild(particle);

        // Animar partícula
        const angle = (Math.PI * 2 * i) / 8;
        const velocity = 50 + Math.random() * 50;
        const dx = Math.cos(angle) * velocity;
        const dy = Math.sin(angle) * velocity;

        particle.animate([
            {transform: 'translate(0, 0) scale(1)', opacity: 1},
            {transform: `translate(${dx}px, ${dy}px) scale(0)`, opacity: 0}
        ], {
            duration: 600,
            easing: 'ease-out'
        }).onfinish = () => particle.remove();
    }
}

// =======================================================
// FUNCIONES PARA TEMPORIZADOR DE DESCANSO
// =======================================================
let activeTimers = {};

function startRestTimer(button, minutes) {
    const timerBox = button.closest('.rest-timer-box');
    const display = timerBox.querySelector('.rest-display');
    const timerId = Date.now();

    // Si ya hay un timer activo en este box, cancelarlo
    if (timerBox.dataset.timerId) {
        clearInterval(activeTimers[timerBox.dataset.timerId]);
        delete activeTimers[timerBox.dataset.timerId];
    }

    let totalSeconds = minutes * 60;
    timerBox.dataset.timerId = timerId;

    // Cambiar botón a "Detener"
    button.innerHTML = '<i class="fas fa-stop mr-1"></i> Detener';
    button.classList.remove('bg-cyan-900/50', 'text-cyan-300', 'border-cyan-500/30');
    button.classList.add('bg-red-900/50', 'text-red-300', 'border-red-500/30');
    button.onclick = function () {
        stopRestTimer(this, minutes);
    };

    // Añadir clase de animación
    timerBox.classList.add('timer-active');

    function updateDisplay() {
        const mins = Math.floor(totalSeconds / 60);
        const secs = totalSeconds % 60;
        display.textContent = mins + ':' + secs.toString().padStart(2, '0');

        if (totalSeconds <= 10 && totalSeconds > 0) {
            display.classList.add('text-yellow-400', 'animate-pulse');
            display.classList.remove('text-cyan-400');
        }

        if (totalSeconds <= 0) {
            clearInterval(activeTimers[timerId]);
            delete activeTimers[timerId];
            display.textContent = '¡LISTO!';
            display.classList.remove('text-yellow-400', 'animate-pulse');
            display.classList.add('text-green-400');
            timerBox.classList.remove('timer-active');
            timerBox.classList.add('timer-finished');

            // Reproducir sonido de notificación (si está disponible)
            playTimerSound();

            // Restaurar botón después de 3 segundos
            setTimeout(() => {
                resetTimerButton(button, display, timerBox, minutes);
            }, 3000);
        }
        totalSeconds--;
    }

    updateDisplay();
    activeTimers[timerId] = setInterval(updateDisplay, 1000);
}

function stopRestTimer(button, minutes) {
    const timerBox = button.closest('.rest-timer-box');
    const display = timerBox.querySelector('.rest-display');

    if (timerBox.dataset.timerId) {
        clearInterval(activeTimers[timerBox.dataset.timerId]);
        delete activeTimers[timerBox.dataset.timerId];
    }

    resetTimerButton(button, display, timerBox, minutes);
}

function resetTimerButton(button, display, timerBox, minutes) {
    display.textContent = minutes + ' min';
    display.classList.remove('text-yellow-400', 'text-green-400', 'animate-pulse');
    display.classList.add('text-cyan-400');

    button.innerHTML = '<i class="fas fa-play mr-1"></i> Iniciar';
    button.classList.remove('bg-red-900/50', 'text-red-300', 'border-red-500/30');
    button.classList.add('bg-cyan-900/50', 'text-cyan-300', 'border-cyan-500/30');
    button.onclick = function () {
        startRestTimer(this, minutes);
    };

    timerBox.classList.remove('timer-active', 'timer-finished');
    delete timerBox.dataset.timerId;
}

function playTimerSound() {
    try {
        // Crear un sonido simple usando Web Audio API
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.value = 800;
        oscillator.type = 'sine';
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
    } catch (e) {
        console.log('Audio no disponible');
    }
}

if (typeof NotificacionesCodeice === 'undefined') {
    class NotificacionesCodeice {
        constructor() {
            this.container = document.getElementById('notificaciones-container');
            this.notificacionesActivas = [];
            this.sonidosHabilitados = true;
        }

        // Mostrar notificación de puntos ganados
        mostrarPuntosGanados(puntos, desglose = null) {
            const notificacion = {
                tipo: 'puntos-ganados',
                icono: '💰',
                titulo: '¡Puntos Ganados!',
                subtitulo: 'Recompensa de Entrenamiento',
                mensaje: `+${puntos} puntos de poder`,
                detalle: desglose ? `${desglose.base} base + ${desglose.bonus} bonus + ${desglose.pruebas} pruebas` : null,
                duracion: 4000
            };

            this.mostrarNotificacion(notificacion);
        }

        // Mostrar notificación de prueba completada
        mostrarPruebaCompletada(nombrePrueba, puntosRecompensa, descripcion = null) {
            const notificacion = {
                tipo: 'prueba-completada',
                icono: '⚔️',
                titulo: '¡Prueba Completada!',
                subtitulo: nombrePrueba,
                mensaje: `Has superado el desafío legendario`,
                detalle: descripcion || `+${puntosRecompensa} puntos de recompensa`,
                duracion: 6000,
                efectos: true
            };

            this.mostrarNotificacion(notificacion);
        }

        // Mostrar notificación de ascensión
        mostrarAscension(nivelAnterior, nivelNuevo, filosofia = null) {
            const notificacion = {
                tipo: 'ascension',
                icono: '🔥',
                titulo: '¡ASCENSIÓN!',
                subtitulo: `${nivelAnterior} → ${nivelNuevo}`,
                mensaje: `Has alcanzado un nuevo nivel de poder`,
                detalle: filosofia ? `"${filosofia}"` : 'Tu leyenda continúa creciendo',
                duracion: 8000,
                efectos: true,
                particulas: true
            };

            this.mostrarNotificacion(notificacion);
        }

        // Mostrar notificación de racha
        mostrarRacha(dias) {
            if (dias < 3) return; // Solo mostrar rachas significativas

            const notificacion = {
                tipo: 'puntos-ganados',
                icono: '🔥',
                titulo: '¡Racha de Fuego!',
                subtitulo: `${dias} días consecutivos`,
                mensaje: `Tu dedicación arde como una llama eterna`,
                detalle: `Bonus de constancia: +${Math.min(15, dias)} puntos`,
                duracion: 5000
            };

            this.mostrarNotificacion(notificacion);
        }

        // Función principal para mostrar notificaciones
        mostrarNotificacion(config) {
            const notifElement = this.crearElementoNotificacion(config);
            this.container.appendChild(notifElement);
            this.notificacionesActivas.push(notifElement);

            // Mostrar con animación
            setTimeout(() => {
                notifElement.classList.add('mostrar');
            }, 100);

            // Añadir efectos especiales
            if (config.efectos) {
                this.añadirEfectosPulso(notifElement);
            }

            if (config.particulas) {
                this.añadirParticulas(notifElement);
            }

            // Auto-ocultar después de la duración especificada
            setTimeout(() => {
                this.ocultarNotificacion(notifElement);
            }, config.duracion);

            // Reposicionar notificaciones existentes
            this.reposicionarNotificaciones();
        }

        // Crear elemento HTML de la notificación
        crearElementoNotificacion(config) {
            const notif = document.createElement('div');
            notif.className = `notificacion-epica ${config.tipo}`;

            notif.innerHTML = `
                <button class="notif-cerrar" onclick="notificacionesCodeice.ocultarNotificacion(this.parentElement)">&times;</button>

                <div class="notif-header">
                    <div class="notif-icono">${config.icono}</div>
                    <div>
                        <div class="notif-titulo">${config.titulo}</div>
                        <div class="notif-subtitulo">${config.subtitulo}</div>
                    </div>
                </div>

                <div class="notif-contenido">
                    <div class="notif-mensaje">${config.mensaje}</div>
                    ${config.detalle ? `<div class="notif-detalle">${config.detalle}</div>` : ''}
                </div>
            `;

            return notif;
        }

        // Ocultar notificación
        ocultarNotificacion(elemento) {
            elemento.classList.add('ocultar');

            setTimeout(() => {
                if (elemento.parentNode) {
                    elemento.parentNode.removeChild(elemento);
                }

                const index = this.notificacionesActivas.indexOf(elemento);
                if (index > -1) {
                    this.notificacionesActivas.splice(index, 1);
                }

                this.reposicionarNotificaciones();
            }, 800);
        }

        // Reposicionar notificaciones para evitar solapamiento
        reposicionarNotificaciones() {
            let offset = 20;
            this.notificacionesActivas.forEach((notif, index) => {
                if (notif.classList.contains('mostrar') && !notif.classList.contains('ocultar')) {
                    notif.style.top = `${offset}px`;
                    offset += notif.offsetHeight + 15;
                }
            });
        }

        // Añadir efectos de pulso
        añadirEfectosPulso(elemento) {
            // Implementación opcional
        }

        // Añadir partículas para ascensiones
        añadirParticulas(elemento) {
            const particulasContainer = document.createElement('div');
            particulasContainer.className = 'particulas';

            for (let i = 0; i < 15; i++) {
                const particula = document.createElement('div');
                particula.className = 'particula';
                particula.style.left = `${Math.random() * 100}%`;
                particula.style.animationDelay = `${Math.random() * 2}s`;
                particula.style.animationDuration = `${2 + Math.random() * 2}s`;
                particulasContainer.appendChild(particula);
            }

            elemento.appendChild(particulasContainer);

            setTimeout(() => {
                if (particulasContainer.parentNode) {
                    particulasContainer.parentNode.removeChild(particulasContainer);
                }
            }, 4000);
        }

        // Limpiar todas las notificaciones
        limpiarTodas() {
            this.notificacionesActivas.forEach(notif => {
                this.ocultarNotificacion(notif);
            });
        }
    } // end class NotificacionesCodeice
} // end if typeof check

// Instancia global del sistema de notificaciones
if (typeof notificacionesCodeice === 'undefined') {
    var notificacionesCodeice = new NotificacionesCodeice();
}

// Funciones de conveniencia para usar desde otros scripts
function mostrarNotificacionPuntos(puntos, desglose = null) {
    notificacionesCodeice.mostrarPuntosGanados(puntos, desglose);
}

function mostrarNotificacionPrueba(nombre, puntos, descripcion = null) {
    notificacionesCodeice.mostrarPruebaCompletada(nombre, puntos, descripcion);
}

function mostrarNotificacionAscension(anterior, nuevo, filosofia = null) {
    notificacionesCodeice.mostrarAscension(anterior, nuevo, filosofia);
}

function mostrarNotificacionRacha(dias) {
    notificacionesCodeice.mostrarRacha(dias);
}

console.log('🎮 Sistema de notificaciones épicas cargado');

document.addEventListener('DOMContentLoaded', function () {
    // Efectos adicionales de interactividad
    const ejercicioCards = document.querySelectorAll('.cyber-ejercicio-card');
    ejercicioCards.forEach(card => {
        card.addEventListener('mouseenter', function () {
            this.style.transform = 'translateY(-3px)';
        });

        card.addEventListener('mouseleave', function () {
            this.style.transform = 'translateY(0)';
        });
    });

    // Efectos para inputs
    const inputs = document.querySelectorAll('.cyber-form-control, .cyber-textarea');
    inputs.forEach(input => {
        input.addEventListener('focus', function () {
            this.parentNode.style.transform = 'scale(1.02)';
            this.parentNode.style.zIndex = '10';
        });

        input.addEventListener('blur', function () {
            this.parentNode.style.transform = 'scale(1)';
            this.parentNode.style.zIndex = '1';
        });
    });

    // Efectos para checkboxes
    const checkboxes = document.querySelectorAll('.cyber-form-check-input');
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            const row = this.closest('.serie-row');
            if (this.checked) {
                row.classList.add('serie-completada');
                row.style.background = 'rgba(212,168,71,0.08)';
                row.style.borderLeft = '3px solid #d4a847';
                this.style.transform = 'scale(1.2)';
                setTimeout(() => {
                    this.style.transform = 'scale(1)';
                }, 200);
            } else {
                row.classList.remove('serie-completada');
                row.style.background = '';
                row.style.borderLeft = '';
            }
        });

        checkbox.addEventListener('mouseenter', function () {
            this.style.transform = 'scale(1.1)';
        });

        checkbox.addEventListener('mouseleave', function () {
            if (!this.matches(':focus')) {
                this.style.transform = 'scale(1)';
            }
        });
    });

    // Efecto de progreso general
    function updateProgress() {
        const totalCheckboxes = checkboxes.length;
        const checkedBoxes = document.querySelectorAll('.cyber-form-check-input:checked').length;
        const progress = (checkedBoxes / totalCheckboxes) * 100;

        // Actualizar color del botón según progreso
        const finalizarBtn = document.querySelector('.cyber-btn-finalizar');
        if (progress === 100) {
            finalizarBtn.style.background = 'linear-gradient(135deg, #2d6a2d, #4ade80)';
            finalizarBtn.style.boxShadow = '0 0 20px rgba(74,222,128,0.4)';
        } else {
            finalizarBtn.style.background = '';
            finalizarBtn.style.boxShadow = '';
        }
    }

    // Escuchar cambios en checkboxes para actualizar progreso
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', updateProgress);
    });

    // Inicializar progreso
    updateProgress();

    // Efecto de envío del formulario
    const form = document.querySelector('form');
    form.addEventListener('submit', function (e) {
        const submitBtn = document.querySelector('.cyber-btn-finalizar');
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
        submitBtn.disabled = true;

        // Efecto visual de envío
        submitBtn.style.background = 'linear-gradient(135deg, #a07820, #d4a847)';
        submitBtn.style.boxShadow = '0 0 20px rgba(212,168,71,0.4)';

        // --- INYECCIÓN DE DATOS DE SESIÓN (RPE, Volumen, etc.) ---
        // Aseguramos que los inputs hidden se envíen incluso si no se usó el modal
        try {
            const resumen = calcularResumenEntrenamiento();
            if (resumen) {
                const addHidden = (name, val) => {
                    let input = form.querySelector(`input[name="${name}"]`);
                    if (!input) {
                        input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = name;
                        form.appendChild(input);
                    }
                    input.value = val;
                };

                // Limpiar 'k' y 'kg' de los valores
                const volumenLimpio = String(resumen.volumen).replace('k', '000').replace(' kg', '').trim();
                const rpeLimpio = resumen.rpeMedio === '-' ? '' : resumen.rpeMedio;

                // Extraer series y ejercicios
                const seriesCompletadas = resumen.series.split('/')[0];
                const seriesTotales = resumen.series.split('/')[1];
                const ejerciciosCompletados = resumen.ejercicios.split('/')[0];
                const ejerciciosTotales = resumen.ejercicios.split('/')[1];

                addHidden('duracion_minutos_real', resumen.tiempo.split(':')[0]);
                addHidden('series_completadas', seriesCompletadas);
                addHidden('series_totales', seriesTotales);
                addHidden('ejercicios_completados', ejerciciosCompletados);
                addHidden('ejercicios_totales', ejerciciosTotales);
                addHidden('volumen_total_sesion', volumenLimpio);
                addHidden('rpe_medio_sesion', rpeLimpio);

                console.log('✅ Datos de sesión inyectados antes del submit:', {rpe: rpeLimpio, vol: volumenLimpio});
            }
        } catch (err) {
            console.error('Error inyectando datos al enviar:', err);
            // No detenemos el envío, permitimos que siga aunque falten datos calculados
        }
    });

    // Validación mejorada
    const requiredInputs = document.querySelectorAll('input[required], textarea[required]');
    requiredInputs.forEach(input => {
        input.addEventListener('invalid', function () {
            this.style.borderColor = 'rgba(220, 53, 69, 0.8)';
            this.style.boxShadow = '0 0 15px rgba(220, 53, 69, 0.4)';
        });

        input.addEventListener('input', function () {
            if (this.validity.valid) {
                this.style.borderColor = 'rgba(0, 255, 255, 0.4)';
                this.style.boxShadow = '';
            }
        });
    });

    // Efecto de carga inicial
    setTimeout(() => {
        document.body.classList.add('loaded');
    }, 500);
});


// FUNCIONES DE TESTING
function testNotificaciones() {
    console.log('🧪 Iniciando test de notificaciones...');

    setTimeout(() => {
        mostrarNotificacionPuntos(47, {base: 25, bonus: 7, pruebas: 15});
    }, 1000);

    setTimeout(() => {
        mostrarNotificacionPrueba("Las Puertas del Esfuerzo", 150, "7 días consecutivos completados");
    }, 3000);

    setTimeout(() => {
        mostrarNotificacionAscension("Rock Lee", "Krillin - El Guerrero Humano", "Tu corazón valiente te hace fuerte");
    }, 5000);

    setTimeout(() => {
        mostrarNotificacionRacha(5);
    }, 7000);
}

// LIMPIAR MENSAJES DJANGO DESPUÉS DE PROCESARLOS
function limpiarMensajesDjango() {
    const djangoMessages = document.querySelectorAll('.alert, .messages li, .message');
    djangoMessages.forEach(msg => {
        if (msg.textContent.includes('CODICE_')) {
            msg.style.display = 'none';
        }
    });
}

setTimeout(limpiarMensajesDjango, 500);

console.log('🎮 Códice de las Leyendas - Sistema de notificaciones cargado');
console.log('🧪 Para probar notificaciones, ejecuta: testNotificaciones()');

// FUNCIONES DE CONVENIENCIA PARA TESTING
function testNotificaciones() {
    console.log('🧪 Iniciando test de notificaciones...');

    // Test puntos
    setTimeout(() => {
        mostrarNotificacionPuntos(47, {base: 25, bonus: 7, pruebas: 15});
    }, 1000);

    // Test prueba
    setTimeout(() => {
        mostrarNotificacionPrueba("Las Puertas del Esfuerzo", 150, "7 días consecutivos completados");
    }, 3000);

    // Test ascensión
    setTimeout(() => {
        mostrarNotificacionAscension("Rock Lee", "Krillin - El Guerrero Humano", "Tu corazón valiente te hace fuerte");
    }, 5000);

    // Test racha
    setTimeout(() => {
        mostrarNotificacionRacha(5);
    }, 7000);
}

// FUNCIÓN PARA LIMPIAR MENSAJES DESPUÉS DE MOSTRAR NOTIFICACIONES
function limpiarMensajesDjango() {
    // Opcional: ocultar los mensajes Django estándar después de procesarlos
    const djangoMessages = document.querySelectorAll('.alert, .messages li, .message');
    djangoMessages.forEach(msg => {
        if (msg.textContent.includes('CODICE_')) {
            msg.style.display = 'none';
        }
    });
}

// Limpiar mensajes después de procesarlos
setTimeout(limpiarMensajesDjango, 500);

// DEBUGGING: Mostrar en consola cuando se carga la página
console.log('🎮 Códice de las Leyendas - Sistema de notificaciones cargado');
console.log('🧪 Para probar notificaciones, ejecuta: testNotificaciones()');

// =======================================================
// FUNCIONES PARA EL PANEL STICKY DE RESUMEN EN TIEMPO REAL
// =======================================================

// Variables globales para el panel sticky
let tiempoInicio = Date.now();
let timerInterval = null;
let volumenAnterior = 0;

// Función para alternar el panel sticky
function toggleStickyPanel() {
    const panel = document.getElementById('sticky-summary-panel');
    const icon = document.getElementById('sticky-toggle-icon');

    if (panel) {
        panel.classList.toggle('minimized');
        localStorage.setItem('sticky_panel_minimized', panel.classList.contains('minimized'));
    }
}

// Función para formatear el tiempo
function formatearTiempo(segundos) {
    const horas = Math.floor(segundos / 3600);
    const minutos = Math.floor((segundos % 3600) / 60);
    const segs = segundos % 60;

    if (horas > 0) {
        return `${horas}:${minutos.toString().padStart(2, '0')}:${segs.toString().padStart(2, '0')}`;
    }
    return `${minutos.toString().padStart(2, '0')}:${segs.toString().padStart(2, '0')}`;
}

// Función para actualizar el tiempo transcurrido
function actualizarTiempoTranscurrido() {
    const tiempoElement = document.getElementById('tiempo-transcurrido');
    if (tiempoElement) {
        const segundosTranscurridos = Math.floor((Date.now() - tiempoInicio) / 1000);
        tiempoElement.textContent = formatearTiempo(segundosTranscurridos);
    }
}

// Función para calcular el volumen acumulado
function calcularVolumenAcumulado() {
    let volumenTotal = 0;

    // Buscar todas las filas de series que estén marcadas como completadas
    const checkboxes = document.querySelectorAll('input[type="checkbox"][name*="_completado_"]:checked');

    checkboxes.forEach(checkbox => {
        const row = checkbox.closest('.serie-row');
        if (row) {
            // Buscar el input de peso en la misma fila
            const pesoInput = row.querySelector('input[name*="_peso_"]');
            const repsInput = row.querySelector('input[name*="_reps_"]');

            if (pesoInput && repsInput) {
                const peso = parseFloat(pesoInput.value.replace(',', '.')) || 0;
                const reps = parseInt(repsInput.value) || 0;
                volumenTotal += peso * reps;
            }
        }
    });

    return Math.round(volumenTotal * 10) / 10; // Redondear a 1 decimal
}

// Función para detectar el ejercicio actual (el primero no completado)
function detectarEjercicioActual() {
    // Buscar todos los headers de ejercicios
    const headers = document.querySelectorAll('.cyber-ejercicio-header');

    for (const header of headers) {
        // Buscar el nombre del ejercicio
        const nombreElement = header.querySelector('.cyber-ejercicio-nombre');
        if (!nombreElement) continue;

        const nombre = nombreElement.textContent.trim();

        // Buscar las series de este ejercicio (siguientes elementos hasta el próximo header)
        let nextElement = header.nextElementSibling;
        let todasCompletadas = true;
        let tieneSeriesReales = false;

        while (nextElement && !nextElement.classList.contains('cyber-ejercicio-header')) {
            if (nextElement.classList.contains('serie-row')) {
                // Solo contar series reales (Serie 1, Serie 2, etc.), no aproximaciones
                const serieLabel = nextElement.querySelector('.serie-cell strong');
                if (serieLabel && serieLabel.textContent.includes('Serie')) {
                    tieneSeriesReales = true;
                    const checkbox = nextElement.querySelector('input[type="checkbox"][name*="_completado_"]');
                    if (checkbox && !checkbox.checked) {
                        todasCompletadas = false;
                        break;
                    }
                }
            }
            nextElement = nextElement.nextElementSibling;
        }

        // Si este ejercicio tiene series no completadas, es el actual
        if (tieneSeriesReales && !todasCompletadas) {
            return nombre;
        }
    }

    return '¡Completado!';
}

// Función principal para actualizar el panel sticky
function actualizarPanelSticky() {
    // Actualizar series completadas
    const seriesElement = document.getElementById('series-completadas-sticky');
    if (seriesElement) {
        const checkboxes = document.querySelectorAll('input[type="checkbox"][name*="_completado_"]');
        const completadas = document.querySelectorAll('input[type="checkbox"][name*="_completado_"]:checked').length;
        // Solo contar series reales, no aproximaciones
        let totalSeriesReales = 0;
        let seriesRealesCompletadas = 0;

        checkboxes.forEach(cb => {
            const row = cb.closest('.serie-row');
            if (row) {
                const serieLabel = row.querySelector('.serie-cell strong');
                if (serieLabel && serieLabel.textContent.includes('Serie')) {
                    totalSeriesReales++;
                    if (cb.checked) seriesRealesCompletadas++;
                }
            }
        });

        seriesElement.textContent = `${seriesRealesCompletadas}/${totalSeriesReales}`;
    }

    // Actualizar volumen acumulado
    const volumenElement = document.getElementById('volumen-acumulado');
    if (volumenElement) {
        const nuevoVolumen = calcularVolumenAcumulado();

        // Animación de pulso si el volumen aumentó
        if (nuevoVolumen > volumenAnterior) {
            volumenElement.classList.add('volume-pulse');
            setTimeout(() => volumenElement.classList.remove('volume-pulse'), 300);
        }

        volumenAnterior = nuevoVolumen;

        // Formatear con separador de miles
        if (nuevoVolumen >= 1000) {
            volumenElement.textContent = (nuevoVolumen / 1000).toFixed(1) + 'k kg';
        } else {
            volumenElement.textContent = nuevoVolumen + ' kg';
        }
    }

    // Actualizar ejercicio actual
    const ejercicioElement = document.getElementById('ejercicio-actual');
    if (ejercicioElement) {
        ejercicioElement.textContent = detectarEjercicioActual();
    }
}

// Inicializar el panel sticky
function initStickyPanel() {
    // Restaurar estado minimizado
    const panel = document.getElementById('sticky-summary-panel');
    if (panel) {
        const isMinimized = localStorage.getItem('sticky_panel_minimized') === 'true';
        if (isMinimized) {
            panel.classList.add('minimized');
        }
    }

    // Iniciar el timer
    timerInterval = setInterval(actualizarTiempoTranscurrido, 1000);

    // Actualizar el panel inicialmente
    actualizarPanelSticky();

    // Escuchar cambios en los checkboxes
    document.querySelectorAll('input[type="checkbox"][name*="_completado_"]').forEach(checkbox => {
        checkbox.addEventListener('change', actualizarPanelSticky);
    });

    // Escuchar cambios en los inputs de peso y reps para actualizar el volumen
    document.querySelectorAll('input[name*="_peso_"], input[name*="_reps_"]').forEach(input => {
        input.addEventListener('change', actualizarPanelSticky);
        input.addEventListener('input', actualizarPanelSticky);
    });

    console.log('📊 Panel sticky de resumen inicializado');
}

// Inicializar cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStickyPanel);
} else {
    initStickyPanel();
}


// Lógica para la barra de progreso sticky
(function () {
    const progressContainer = document.getElementById('workout-progress-container');
    const placeholder = document.getElementById('progress-placeholder');

    if (!progressContainer || !placeholder) return;

    const originalOffsetTop = progressContainer.offsetTop;

    window.addEventListener('scroll', function () {
        const stickyClass = 'progress-bar-sticky';

        if (window.pageYOffset > originalOffsetTop) {
            if (!progressContainer.classList.contains(stickyClass)) {
                // Guardar la altura antes de volverlo fixed
                const height = progressContainer.offsetHeight;
                placeholder.style.height = height + 'px';
                placeholder.style.display = 'block';
                placeholder.style.marginBottom = window.getComputedStyle(progressContainer).marginBottom;

                progressContainer.classList.add(stickyClass);
            }
        } else {
            if (progressContainer.classList.contains(stickyClass)) {
                progressContainer.classList.remove(stickyClass);
                placeholder.style.display = 'none';
            }
        }
    });
})();

function inferStepKg(inputEl) {
    const n = (inputEl.dataset.eqName || "").toLowerCase();
    // mancuernas: si el recomendado viene "por mancuerna", mantenemos 2.5
    if (n.includes("mancuerna") || n.includes("mancuernas") || n.includes("db ")) return 2.5;

    // máquinas/polea (saltos 5kg)
    if (n.includes("máquina") || n.includes("maquina") || n.includes("smith") || n.includes("prensa") || n.includes("hack")) return 5.0;
    if (n.includes("polea") || n.includes("cable") || n.includes("jalón") || n.includes("jalon") || n.includes("pulley")) return 5.0;

    // barra/general
    return 2.5;
}

function safeParseFloat(v) {
    const x = parseFloat(String(v).replace(",", "."));
    return Number.isFinite(x) ? x : 0;
}

function setInputValue(inputEl, val) {
    // 1 decimal para que no se vea "37.500000"
    inputEl.value = (Math.round(val * 10) / 10).toFixed(1);
    inputEl.dispatchEvent(new Event("input", {bubbles: true}));
    inputEl.dispatchEvent(new Event("change", {bubbles: true}));
}

document.addEventListener("click", (e) => {
    const btn = e.target.closest(".quick-btn");
    if (!btn) return;

    const cell = btn.closest(".serie-cell");
    if (!cell) return;

    const input = cell.querySelector("input[type='number']");
    if (!input) return;

    const step = inferStepKg(input);
    const current = safeParseFloat(input.value);
    const rec = safeParseFloat(input.dataset.recWeight);

    if (btn.classList.contains("quick-copy")) {
        setInputValue(input, rec);
    } else if (btn.classList.contains("quick-minus")) {
        setInputValue(input, Math.max(0, current - step));
    } else if (btn.classList.contains("quick-plus")) {
        setInputValue(input, current + step);
    }

    // micro feedback
    if (navigator.vibrate) navigator.vibrate(20);
});
document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-aprox-toggle]");
    if (!btn) return;

    const block = btn.closest("[data-aprox]");
    if (!block) return;

    const content = block.querySelector("[data-aprox-content]");
    if (!content) return;

    const expanded = btn.getAttribute("aria-expanded") === "true";
    btn.setAttribute("aria-expanded", expanded ? "false" : "true");

    if (expanded) {
        content.hidden = true;
    } else {
        content.hidden = false;
    }

    if (navigator.vibrate) navigator.vibrate(20);
});

function clamp(n, min, max) {
    return Math.min(max, Math.max(min, n));
}

function safeParseInt(v) {
    const n = parseInt(String(v), 10);
    return Number.isFinite(n) ? n : 0;
}

function setInputValueInt(inputEl, val) {
    inputEl.value = String(Math.max(0, Math.round(val)));
    inputEl.dispatchEvent(new Event("input", {bubbles: true}));
    inputEl.dispatchEvent(new Event("change", {bubbles: true}));
}

function setInputValueFloat1(inputEl, val) {
    // 1 decimal (para RPE)
    inputEl.value = (Math.round(val * 10) / 10).toFixed(1);
    inputEl.dispatchEvent(new Event("input", {bubbles: true}));
    inputEl.dispatchEvent(new Event("change", {bubbles: true}));
}

document.addEventListener("click", (e) => {
    // === REPS ===
    const repsBtn = e.target.closest(".quick-reps-minus, .quick-reps-plus");
    if (repsBtn) {
        const cell = repsBtn.closest(".serie-cell");
        if (!cell) return;

        const input = cell.querySelector("input.reps-input");
        if (!input) return;

        const current = safeParseInt(input.value);
        const step = 1;

        if (repsBtn.classList.contains("quick-reps-minus")) {
            setInputValueInt(input, current - step);
        } else {
            setInputValueInt(input, current + step);
        }

        if (navigator.vibrate) navigator.vibrate(15);
        return;
    }

    // === RPE ===
    const rpeBtn = e.target.closest(".quick-rpe-minus, .quick-rpe-plus");
    if (rpeBtn) {
        const cell = rpeBtn.closest(".serie-cell");
        if (!cell) return;

        const input = cell.querySelector("input.rpe-input");
        if (!input) return;

        const current = safeParseFloat(input.value); // ya la tienes en tu archivo
        const step = 0.5;

        const min = input.hasAttribute("min") ? safeParseFloat(input.getAttribute("min")) : 0;
        const max = input.hasAttribute("max") ? safeParseFloat(input.getAttribute("max")) : 10;

        if (rpeBtn.classList.contains("quick-rpe-minus")) {
            setInputValueFloat1(input, clamp(current - step, min, max));
        } else {
            setInputValueFloat1(input, clamp(current + step, min, max));
        }

        if (navigator.vibrate) navigator.vibrate(15);
        return;
    }
});

function actualizarSerieActiva() {
    // Lógica de serie-activa eliminada para limpiar el diseño
}

// Llamada inicial
document.addEventListener('DOMContentLoaded', actualizarSerieActiva);

// Cada vez que marcas/desmarcas un checkbox de serie real, recalculamos
document.addEventListener('change', (e) => {
    const cb = e.target.closest('input[type="checkbox"]');
    if (!cb) return;

    const row = cb.closest('.serie-row');
    if (!row) return;

    const strong = row.querySelector('.serie-cell strong');
    const esSerieReal = strong && strong.textContent.includes('Serie');
    if (!esSerieReal) return;

    actualizarSerieActiva();
});

function focusSiguienteSerie(rowActual) {
    // Buscar todas las series reales
    const seriesReales = Array.from(document.querySelectorAll('.serie-row')).filter(row => {
        const strong = row.querySelector('.serie-cell strong');
        return strong && strong.textContent.includes('Serie');
    });

    const idx = seriesReales.indexOf(rowActual);
    if (idx === -1) return;

    const siguiente = seriesReales[idx + 1];
    if (!siguiente) return;

    // Inputs de la siguiente serie
    const pesoInput = siguiente.querySelector('.serie-cell[data-label*="Peso"] input');
    const repsInput = siguiente.querySelector('.serie-cell[data-label="Reps Realizadas"] input');

    // Decidir foco: peso si está vacío, si no reps
    if (pesoInput && (!pesoInput.value || pesoInput.value === "0")) {
        pesoInput.focus({preventScroll: true});
    } else if (repsInput) {
        repsInput.focus({preventScroll: true});
    }

    // Scroll suave si hace falta (solo si está fuera de viewport)
    const rect = siguiente.getBoundingClientRect();
    if (rect.top < 0 || rect.bottom > window.innerHeight) {
        siguiente.scrollIntoView({behavior: 'smooth', block: 'center'});
    }
}

function markError(inputEl, msg) {
    if (!inputEl) return;
    inputEl.classList.add("input-error");
    inputEl.addEventListener("input", () => inputEl.classList.remove("input-error"), {once: true});

    // hint debajo (1 por fila)
    const row = inputEl.closest(".serie-row");
    if (!row) return;

    let hint = row.querySelector(".input-hint");
    if (!hint) {
        hint = document.createElement("div");
        hint.className = "input-hint";
        row.appendChild(hint);
    }
    hint.textContent = msg;
    setTimeout(() => {
        if (hint) hint.remove();
    }, 2500);
}

document.addEventListener("click", (e) => {
    const cb = e.target.closest('input[type="checkbox"][name*="_completado_"]');
    if (!cb) return;

    const row = cb.closest(".serie-row");
    if (!row) return;

    const strong = row.querySelector('.serie-cell strong');
    const esSerieReal = strong && strong.textContent.includes('Serie');
    if (!esSerieReal) return;

    // Inputs requeridos en esa fila
    const pesoInput = row.querySelector('.serie-cell[data-label*="Peso"] input');
    const repsInput = row.querySelector('.serie-cell[data-label="Reps Realizadas"] input');

    const peso = pesoInput ? parseFloat((pesoInput.value || "").replace(",", ".")) : 0;
    const reps = repsInput ? parseInt(repsInput.value, 10) : 0;
    const nombreEjercicio = row.closest('.cyber-ejercicio-card').querySelector('.cyber-ejercicio-nombre')?.textContent || '';

    // Si intenta marcar y falta algo, bloquea
    if (!cb.checked) { // aún no está marcado; está intentando marcarlo
        let ok = true;
        // Si es peso corporal, el peso puede ser 0
        if (!esPesoCorporal(nombreEjercicio)) {
            if (!pesoInput || !Number.isFinite(peso) || peso <= 0) {
                ok = false;
                markError(pesoInput, "Falta el peso (o es 0).");
                if (navigator.vibrate) navigator.vibrate(40);
            }
        }
        if (!repsInput || !Number.isFinite(reps) || reps <= 0) {
            ok = false;
            markError(repsInput, "Faltan las reps (o es 0).");
            if (navigator.vibrate) navigator.vibrate(40);
        }
        if (!ok) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }
    }
}, true);

function parseNum(v) {
    const x = parseFloat(String(v || "").replace(",", "."));
    return Number.isFinite(x) ? x : 0;
}

function findExerciseScopeFromRow(row) {
    // Subimos hasta encontrar un contenedor que incluya varias .serie-row y el summary
    let scope = row.parentElement;
    for (let i = 0; i < 10 && scope; i++) {
        if (scope.querySelector && scope.querySelector('[data-ex-summary]')) return scope;
        scope = scope.parentElement;
    }
    return null;
}

function computeExerciseSummary(scope) {
    const rows = Array.from(scope.querySelectorAll('.serie-row')).filter(r => {
        const strong = r.querySelector('.serie-cell strong');
        return strong && strong.textContent.includes('Serie'); // solo series reales
    });

    const summary = scope.querySelector('[data-ex-summary]');
    if (!summary) return;

    const total = rows.length;
    let done = 0;
    let volume = 0;
    let rpeSum = 0, rpeN = 0;

    let best = {reps: 0, peso: 0, rpe: 0};

    rows.forEach(r => {
        const cb = r.querySelector('input[type="checkbox"][name*="_completado_"]');
        const checked = cb && cb.checked;

        const pesoInput = r.querySelector('.serie-cell[data-label*="Peso"] input');
        const repsInput = r.querySelector('.serie-cell[data-label="Reps Realizadas"] input');
        const rpeInput = r.querySelector('.serie-cell[data-label="RPE Sentido"] input');

        const peso = parseNum(pesoInput && pesoInput.value);
        const reps = parseNum(repsInput && repsInput.value);
        const rpe = parseNum(rpeInput && rpeInput.value);

        if (checked) {
            done += 1;
            if (peso > 0 && reps > 0) volume += (peso * reps);

            if (rpe > 0) {
                rpeSum += rpe;
                rpeN += 1;
            }

            // mejor serie: más reps; si empata, más peso
            if (reps > best.reps || (reps === best.reps && peso > best.peso)) {
                best = {reps, peso, rpe};
            }
        }
    });

    // pintar
    summary.querySelector('[data-ex-sum-series]').textContent = `${done}/${total}`;
    summary.querySelector('[data-ex-sum-volume]').textContent = `${Math.round(volume)} kg`;

    if (done > 0) {
        summary.hidden = false;
        summary.querySelector('[data-ex-sum-best]').textContent =
            best.reps > 0 ? `${best.peso.toFixed(1)} kg × ${best.reps} reps` : '-';
        summary.querySelector('[data-ex-sum-rpe]').textContent =
            rpeN > 0 ? (Math.round((rpeSum / rpeN) * 10) / 10).toFixed(1) : '-';
    } else {
        summary.hidden = true;
    }
}

function recomputeFromAnyRow(row) {
    const scope = findExerciseScopeFromRow(row);
    if (!scope) return;
    computeExerciseSummary(scope);
}

// Recalcular cuando:
document.addEventListener('change', (e) => {
    const row = e.target.closest('.serie-row');
    if (!row) return;
    const strong = row.querySelector('.serie-cell strong');
    if (!strong || !strong.textContent.includes('Serie')) return;
    recomputeFromAnyRow(row);
});

document.addEventListener('input', (e) => {
    const row = e.target.closest('.serie-row');
    if (!row) return;
    const strong = row.querySelector('.serie-cell strong');
    if (!strong || !strong.textContent.includes('Serie')) return;
    recomputeFromAnyRow(row);
});

// Inicial
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.serie-row').forEach(r => {
        const strong = r.querySelector('.serie-cell strong');
        if (strong && strong.textContent.includes('Serie')) recomputeFromAnyRow(r);
    });
});

(function () {
    function parseFloatSafe(v) {
        if (v == null) return NaN;
        const s = String(v).replace(",", ".");
        const n = parseFloat(s);
        return Number.isFinite(n) ? n : NaN;
    }

    function parseIntSafe(v) {
        const n = parseInt(v, 10);
        return Number.isFinite(n) ? n : NaN;
    }

    function getRpeHint({setIndex, totalSets, rpeTarget, rpeFelt, repsDone, repsMin, repsMax, incKg}) {
        const delta = rpeFelt - rpeTarget;
        const isFirst = setIndex === 1;
        const isLast = setIndex === totalSets;

        if (!Number.isFinite(rpeTarget) || !Number.isFinite(rpeFelt)) return null;

        // ΔRPE <= -2
        if (delta <= -2) {
            if (isLast) return {sev: "info", msg: "Muy conservador. Última serie: prioriza técnica y termina sólido."};
            return {sev: "info", msg: `Demasiado fácil. Sube ${incKg}–${incKg * 2} kg en la próxima serie.`};
        }

        // ΔRPE = -1
        if (delta === -1) {
            if (isLast) return {sev: "info", msg: "Un poco fácil. Apunta a subir carga o reps la próxima sesión."};
            return {
                sev: "info",
                msg: `Carga conservadora. Puedes subir ${incKg}–${incKg * 2} kg en la siguiente serie.`
            };
        }

        // ΔRPE = 0
        if (delta === 0) return {sev: "info", msg: "Serie ideal. Mantén carga y reps."};

        // ΔRPE = +1
        if (delta === 1) {
            if (isFirst) return {sev: "warn", msg: "Un poco más exigente en la serie 1. Mantén y observa la próxima."};
            return {sev: "warn", msg: "Algo más exigente de lo esperado. Mantén carga y observa la siguiente."};
        }

        // ΔRPE >= +2
        if (delta >= 2) {
            if (isLast) return {sev: "danger", msg: "RPE alto. Última serie: baja 1–2 reps y protege técnica."};
            return {sev: "danger", msg: `RPE alto. Reduce ${incKg}–${incKg * 2} kg o baja 1–2 reps en la próxima.`};
        }

        return null;
    }

    function sevStyle(sev) {
        // ajusta a tu estética: neón pero legible
        if (sev === "danger") return "color:#ff4d7d";
        if (sev === "warn") return "color:#ffd166";
        return "color:#62e6ff";
    }

    function updateHintForSet(exerciseEl, setIndex) {
        const rpeTarget = parseFloatSafe(exerciseEl.dataset.rpeTarget);
        const repsMin = parseIntSafe(exerciseEl.dataset.repsMin);
        const repsMax = parseIntSafe(exerciseEl.dataset.repsMax);
        const incKg = parseFloatSafe(exerciseEl.dataset.incKg);
        const totalSets = parseIntSafe(exerciseEl.dataset.totalSets);

        const rpeEl = exerciseEl.querySelector(`.rpe-input[data-set="${setIndex}"]`);
        const repsEl = exerciseEl.querySelector(`.reps-input[data-set="${setIndex}"]`);
        const hintEl = exerciseEl.querySelector(`.rpe-hint[data-set="${setIndex}"]`);

        if (!rpeEl || !repsEl || !hintEl) return;

        const rpeFelt = parseFloatSafe(rpeEl.value);
        const repsDone = parseIntSafe(repsEl.value);

        const hint = getRpeHint({
            setIndex,
            totalSets,
            rpeTarget,
            rpeFelt,
            repsDone,
            repsMin,
            repsMax,
            incKg: Number.isFinite(incKg) ? incKg : 2.5
        });

        if (!hint) {
            hintEl.textContent = "";
            hintEl.removeAttribute("class");
            hintEl.classList.add("rpe-hint");
            return;
        }

        // Determinar los estilos del chip según la severidad
        let chipClass = "rpe-hint-chip";
        let chipColor = "#4ade80"; // verde por defecto (info)
        let chipBorder = "rgba(34,197,94,0.35)";
        let chipBg = "rgba(34,197,94,0.10)";
        let chipIcon = "✓";

        if (hint.sev === "warn") {
            chipColor = "#fbbf24"; // amarillo
            chipBorder = "rgba(251,191,36,0.35)";
            chipBg = "rgba(251,191,36,0.10)";
            chipIcon = "⚠";
        } else if (hint.sev === "danger") {
            chipColor = "#f87171"; // rojo
            chipBorder = "rgba(248,113,113,0.35)";
            chipBg = "rgba(248,113,113,0.10)";
            chipIcon = "⚡";
        }

        hintEl.className = chipClass;
        hintEl.setAttribute("style", `color: ${chipColor}; border-color: ${chipBorder}; background-color: ${chipBg};`);
        hintEl.textContent = chipIcon + " " + hint.msg;
    }

    // Listeners: al escribir en RPE/reps, o al marcar "Hecho"
    document.querySelectorAll(".exercise").forEach(exerciseEl => {


        exerciseEl.addEventListener("change", (e) => {
            const t = e.target;
            if (!t || !t.dataset) return;
            if (!t.classList.contains("done-input")) return;
            const setIndex = parseIntSafe(t.dataset.set);
            if (!Number.isFinite(setIndex)) return;
            updateHintForSet(exerciseEl, setIndex);
        });
    });
})();

// =======================================================
// INDICADOR VISUAL DE SERIE ACTIVA/COMPLETADA/PENDIENTE
// =======================================================
function updateSerieStates() {
    // Buscar todos los ejercicios dentro del formulario
    const form = document.querySelector('form[action*="guardar_entrenamiento"]');
    if (!form) return;

    const ejercicioCards = form.querySelectorAll('.cyber-ejercicio-card:not(.cyber-resumen-section)');

    ejercicioCards.forEach((card) => {
        // Buscar todas las series efectivas (no aproximaciones) de este ejercicio
        const seriesRows = card.querySelectorAll('.serie-row:not(.serie-aproximacion)');

        let foundSiguiente = false;

        seriesRows.forEach((row) => {
            const checkbox = row.querySelector('input[type="checkbox"][name*="_completado_"]');
            if (!checkbox) return;

            // Quitar todas las clases de estado
            row.classList.remove('serie-completada', 'serie-siguiente', 'serie-pendiente');

            if (checkbox.checked) {
                // Serie completada
                row.classList.add('serie-completada');
            } else if (!foundSiguiente) {
                // Primera serie no completada = siguiente
                row.classList.add('serie-siguiente');
                foundSiguiente = true;
            } else {
                // Series después de la siguiente = pendientes
                row.classList.add('serie-pendiente');
            }
        });
    });
}

// =======================================================
// INDICADOR VISUAL DE EJERCICIO ACTIVO/COMPLETADO
// =======================================================
function updateExerciseStates() {
    const form = document.querySelector('form[action*="guardar_entrenamiento"]');
    if (!form) return;

    const ejercicioCards = form.querySelectorAll('.cyber-ejercicio-card:not(.cyber-resumen-section)');
    let foundActive = false;

    ejercicioCards.forEach((card) => {
        const checkboxes = card.querySelectorAll('.serie-row:not(.serie-aproximacion) input[type="checkbox"][name*="_completado_"]');

        if (checkboxes.length === 0) return;

        const totalSeries = checkboxes.length;
        const completadas = Array.from(checkboxes).filter(cb => cb.checked).length;

        card.classList.remove('ejercicio-completado', 'ejercicio-activo', 'ejercicio-pendiente');

        if (completadas === totalSeries && totalSeries > 0) {
            card.classList.add('ejercicio-completado');
        } else if (!foundActive) {
            card.classList.add('ejercicio-activo');
            foundActive = true;
        } else {
            card.classList.add('ejercicio-pendiente');
        }
    });
}

// Escuchar cambios en los checkboxes
document.addEventListener('change', (e) => {
    if (e.target.matches('input[type="checkbox"][name*="_completado_"]')) {
        updateSerieStates();
        updateExerciseStates();
    }
});

// Inicializar estados al cargar la página
document.addEventListener('DOMContentLoaded', () => {
    updateSerieStates();
    updateExerciseStates();
});

// =======================================================
// MODAL DE RESUMEN DEL ENTRENAMIENTO
// =======================================================
function calcularResumenEntrenamiento() {
    // Buscar el formulario de forma más flexible
    let form = document.querySelector('form[action*="guardar_entrenamiento"]');
    if (!form) {
        form = document.querySelector('form[method="POST"]');
    }
    if (!form) {
        form = document.querySelector('form');
    }

    console.log('Form encontrado:', form);

    if (!form) {
        console.error('No se encontró ningún formulario');
        return null;
    }

    const ejercicioCards = form.querySelectorAll('.cyber-ejercicio-card:not(.cyber-resumen-section)');
    console.log('Ejercicios encontrados:', ejercicioCards.length);

    let totalSeries = 0;
    let seriesCompletadas = 0;
    let volumenTotal = 0;
    let ejerciciosCompletados = 0;
    let totalEjercicios = 0;
    let rpeTotal = 0;
    let rpeCount = 0;

    const ejerciciosData = [];

    ejercicioCards.forEach((card) => {
        const nombreEl = card.querySelector('.cyber-ejercicio-header h4');
        const nombre = nombreEl ? nombreEl.textContent.trim().replace(/^[^\w]*/, '') : 'Ejercicio';

        const checkboxes = card.querySelectorAll('.serie-row:not(.serie-aproximacion) input[type="checkbox"][name*="_completado_"]');

        if (checkboxes.length === 0) return;

        totalEjercicios++;
        let ejSeries = checkboxes.length;
        let ejCompletadas = 0;
        let ejVolumen = 0;
        let ejRpeSum = 0;
        let ejRpeCount = 0;
        let ejMaxPeso = 0;

        checkboxes.forEach((cb) => {
            totalSeries++;
            if (cb.checked) {
                seriesCompletadas++;
                ejCompletadas++;

                const row = cb.closest('.serie-row');
                if (row) {
                    const pesoInput = row.querySelector('.serie-cell[data-label*="Peso"] input');
                    const repsInput = row.querySelector('.serie-cell[data-label="Reps Realizadas"] input');
                    const rpeInput = row.querySelector('.serie-cell[data-label="RPE Sentido"] input');

                    const peso = pesoInput ? parseFloat(pesoInput.value.replace(',', '.')) || 0 : 0;
                    const reps = repsInput ? parseInt(repsInput.value) || 0 : 0;
                    const rpe = rpeInput ? parseFloat(rpeInput.value.replace(',', '.')) || 0 : 0;

                    ejVolumen += peso * reps;
                    if (peso > ejMaxPeso) ejMaxPeso = peso;

                    if (rpe > 0) {
                        ejRpeSum += rpe;
                        ejRpeCount++;
                        rpeTotal += rpe;
                        rpeCount++;
                    }
                }
            }
        });

        volumenTotal += ejVolumen;

        if (ejCompletadas === ejSeries && ejSeries > 0) {
            ejerciciosCompletados++;
        }

        if (ejCompletadas > 0) {
            // Obtener datos históricos del input oculto
            const historialEl = card.querySelector('.ejercicio-historial');
            const pesoAnterior = historialEl ? parseFloat(historialEl.dataset.pesoAnterior) : 0;
            const volAnterior = historialEl ? parseFloat(historialEl.dataset.volumenAnterior) : 0;
            const prPeso = historialEl ? parseFloat(historialEl.dataset.prPeso) : 0;
            const prReps = historialEl ? parseInt(historialEl.dataset.prReps) : 0;

            // Calcular mejoras
            let mejoraPeso = 0;
            if (pesoAnterior > 0 && ejMaxPeso > pesoAnterior) {
                mejoraPeso = ejMaxPeso - pesoAnterior;
            }

            let mejoraVol = 0;
            if (volAnterior > 0 && ejVolumen > volAnterior) {
                mejoraVol = ((ejVolumen - volAnterior) / volAnterior * 100);
            }

            // Detectar PR (Récord Personal)
            // Un PR se bate si el peso actual es mayor al PR histórico,
            // o si es el mismo peso pero con más repeticiones (simplificado aquí a peso)
            const esNuevoPR = ejMaxPeso > prPeso && ejMaxPeso > 0;

            ejerciciosData.push({
                nombre: nombre,
                series: `${ejCompletadas}/${ejSeries}`,
                volumen: Math.round(ejVolumen),
                rpe: ejRpeCount > 0 ? (ejRpeSum / ejRpeCount).toFixed(1) : '-',
                mejoraPeso: mejoraPeso,
                mejoraVol: mejoraVol,
                esNuevoPR: esNuevoPR,
                maxPeso: ejMaxPeso
            });
        }
    });

    // Obtener tiempo
    const tiempoEl = document.getElementById('tiempo-transcurrido');
    const tiempo = tiempoEl ? tiempoEl.textContent : '00:00';

    return {
        tiempo,
        series: `${seriesCompletadas}/${totalSeries}`,
        volumen: volumenTotal >= 1000 ? (volumenTotal / 1000).toFixed(1) + 'k' : Math.round(volumenTotal),
        ejercicios: `${ejerciciosCompletados}/${totalEjercicios}`,
        rpeMedio: rpeCount > 0 ? (rpeTotal / rpeCount).toFixed(1) : '-',
        ejerciciosData
    };
}

function mostrarModalResumen() {
    console.log('Entrando a mostrarModalResumen');
    try {
        const resumen = calcularResumenEntrenamiento();
        console.log('Resumen calculado:', resumen);
        if (!resumen) {
            console.error('No se pudo calcular el resumen');
            return;
        }

        // Actualizar stats
        document.getElementById('modal-tiempo').textContent = resumen.tiempo;
        document.getElementById('modal-series').textContent = resumen.series;
        document.getElementById('modal-volumen').textContent = resumen.volumen + ' kg';
        document.getElementById('modal-ejercicios').textContent = resumen.ejercicios;
        document.getElementById('modal-rpe-medio').textContent = resumen.rpeMedio;

        // Generar lista de ejercicios
        const listaEl = document.getElementById('modal-ejercicios-lista');
        listaEl.innerHTML = '';

        resumen.ejerciciosData.forEach((ej) => {
            const item = document.createElement('div');
            item.className = 'ejercicio-resumen-item';

            // Construir indicadores de mejora
            let indicadoresHTML = '';
            if (ej.esNuevoPR) {
                indicadoresHTML += `<span class="badge-pr" title="¡Nuevo Récord Personal!"><i class="fas fa-crown"></i> PR</span>`;
            } else if (ej.mejoraPeso > 0) {
                indicadoresHTML += `<span class="badge-mejora" title="Mejora de carga"><i class="fas fa-arrow-up"></i> +${ej.mejoraPeso}kg</span>`;
            }

            if (ej.mejoraVol > 5) { // Solo mostrar si la mejora es significativa (>5%)
                indicadoresHTML += `<span class="badge-vol" title="Mejora de volumen"><i class="fas fa-chart-line"></i> +${Math.round(ej.mejoraVol)}% vol</span>`;
            }

            item.innerHTML = `
                <i class="fas ${ej.esNuevoPR ? 'fa-trophy text-yellow-400' : 'fa-check-circle ej-icon'}"></i>
                <div class="ej-info">
                    <span class="ej-nombre">${ej.nombre}</span>
                    <div class="ej-badges">${indicadoresHTML}</div>
                </div>
                <div class="ej-stats">
                    <span class="ej-sets">${ej.series} series</span>
                    <span class="ej-vol">Vol: ${ej.volumen} kg</span>
                </div>
            `;
            listaEl.appendChild(item);
        });

        if (resumen.ejerciciosData.length === 0) {
            listaEl.innerHTML = '<p style="text-align: center; color: rgba(255,255,255,0.5); padding: 15px;">No hay ejercicios completados aún</p>';
        }

        // Mostrar modal
        console.log('Mostrando modal...');
        document.getElementById('modal-resumen-overlay').classList.add('active');
        document.body.style.overflow = 'hidden';
        console.log('Modal mostrado');
    } catch (error) {
        console.error('Error en mostrarModalResumen:', error);
        alert('Error al mostrar resumen: ' + error.message);
    }
}

function cerrarModalResumen() {
    document.getElementById('modal-resumen-overlay').classList.remove('active');
    document.body.style.overflow = '';
}

// Event listeners del modal
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM Cargado - Inicializando modal...');

    // Botón para mostrar resumen
    const btnMostrarResumen = document.getElementById('btn-mostrar-resumen');
    console.log('Botón mostrar resumen:', btnMostrarResumen);

    if (btnMostrarResumen) {
        btnMostrarResumen.addEventListener('click', function () {
            console.log('Click en Finalizar y Guardar');
            mostrarModalResumen();
        });
        console.log('Event listener añadido al botón');
    } else {
        console.error('ERROR: No se encontró el botón btn-mostrar-resumen');
    }

    // Botón volver a editar
    const btnVolverEditar = document.getElementById('btn-volver-editar');
    if (btnVolverEditar) {
        btnVolverEditar.addEventListener('click', cerrarModalResumen);
    }

    // Botón confirmar y guardar
    const btnConfirmarGuardar = document.getElementById('btn-confirmar-guardar');
    if (btnConfirmarGuardar) {
        btnConfirmarGuardar.addEventListener('click', function () {
            console.log('Botón guardar clickeado');

            // Cerrar modal
            cerrarModalResumen();

            // Cambiar apariencia del botón
            const btnPrincipal = document.getElementById('btn-mostrar-resumen');
            if (btnPrincipal) {
                btnPrincipal.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
                btnPrincipal.disabled = true;
            }

            // Buscar el formulario
            const form = document.querySelector('form');
            console.log('Form encontrado:', form);

            if (form) {
                console.log('Enviando formulario...');

                // --- NUEVO: Agregar datos de gamificación como hidden inputs ---
                const resumen = calcularResumenEntrenamiento();
                if (resumen) {
                    const addHidden = (name, val) => {
                        let input = form.querySelector(`input[name="${name}"]`);
                        if (!input) {
                            input = document.createElement('input');
                            input.type = 'hidden';
                            input.name = name;
                            form.appendChild(input);
                        }
                        input.value = val;
                    };

                    // Limpiar 'k' y 'kg' de los valores
                    const volumenLimpio = String(resumen.volumen).replace('k', '000').replace(' kg', '').trim();
                    const rpeLimpio = resumen.rpeMedio === '-' ? '' : resumen.rpeMedio;

                    // Extraer series y ejercicios (ej: "5/10" -> 5)
                    const seriesCompletadas = resumen.series.split('/')[0];
                    const seriesTotales = resumen.series.split('/')[1];
                    const ejerciciosCompletados = resumen.ejercicios.split('/')[0];
                    const ejerciciosTotales = resumen.ejercicios.split('/')[1];

                    addHidden('duracion_minutos_real', resumen.tiempo.split(':')[0]); // simplificado
                    addHidden('series_completadas', seriesCompletadas);
                    addHidden('series_totales', seriesTotales);
                    addHidden('ejercicios_completados', ejerciciosCompletados);
                    addHidden('ejercicios_totales', ejerciciosTotales);
                    addHidden('volumen_total_sesion', volumenLimpio);
                    addHidden('rpe_medio_sesion', rpeLimpio);
                }

                form.submit();
            } else {
                console.error('No se encontró el formulario');
                alert('Error: No se encontró el formulario');
            }
        });
    } else {
        console.error('No se encontró el botón btn-confirmar-guardar');
    }

    // Cerrar al hacer click fuera del modal
    const modalOverlay = document.getElementById('modal-resumen-overlay');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) {
                cerrarModalResumen();
            }
        });
    }

    // Cerrar con ESC
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modalOverlay.classList.contains('active')) {
            cerrarModalResumen();
        }
    });
});


// Función para detectar si un ejercicio es de peso corporal
function esPesoCorporal(nombre) {
    const n = nombre.toLowerCase();
    return n.includes('pc') || n.includes('peso corporal') || n.includes('dominadas') ||
        n.includes('flexiones') || n.includes('fondos') || n.includes('pull up') ||
        n.includes('chin up') || n.includes('dips') || n.includes('sentadilla al aire');
}

// Función para obtener/guardar el peso base de un ejercicio en localStorage
function getPesoBase(ejercicioId) {
    return parseFloat(localStorage.getItem('peso_base_' + ejercicioId)) || 20;
}

function setPesoBase(ejercicioId, peso) {
    localStorage.setItem('peso_base_' + ejercicioId, peso);
}

function actualizarPesoPorLado(input) {
    const card = input.closest('.cyber-ejercicio-card');
    if (!card) return;

    const nombreEjercicio = card.querySelector('.cyber-ejercicio-nombre')?.textContent || '';
    const ejercicioId = card.dataset.ejercicioId || nombreEjercicio;
    const peso = parseFloat(input.value.replace(',', '.')) || 0;

    const display = input.closest('.serie-cell')?.querySelector('.weight-per-side-display');
    if (!display) return;

    if (esPesoCorporal(nombreEjercicio)) {
        display.innerHTML = '<span style="color: #a855f7; font-weight: bold;">PESO CORPORAL</span>';
        input.value = 0;
        input.readOnly = true;
        input.style.opacity = '0.5';
        return;
    }

    let pesoBarra = getPesoBase(ejercicioId);

    // Si es mancuerna, el peso base es 0 (el peso ya es la mancuerna)
    if (nombreEjercicio.toLowerCase().includes('mancuerna')) {
        pesoBarra = 0;
    }

    const pesoDiscos = peso - pesoBarra;
    const pesoPorLado = pesoDiscos / 2;

    if (peso > 0 && pesoPorLado >= 0) {
        const formattedWeight = pesoPorLado.toFixed(1).replace('.', ',');
        display.innerHTML = `+<span class="side-weight-value" style="color: #a855f7; font-weight: bold;">${formattedWeight}</span> kg/lado <button type="button" onclick="configurarPesoBase('${ejercicioId}', this)" style="background: none; border: none; color: #475569; font-size: 0.7rem; cursor: pointer; margin-left: 5px;"><i class="fas fa-cog"></i></button>`;
    } else {
        display.innerHTML = `<button type="button" onclick="configurarPesoBase('${ejercicioId}', this)" style="background: none; border: none; color: #475569; font-size: 0.7rem; cursor: pointer;"><i class="fas fa-cog"></i> Config. Base</button>`;
    }
}

window.configurarPesoBase = function (ejercicioId, btn) {
    const actual = getPesoBase(ejercicioId);
    const nuevo = prompt(`Configurar peso base (barra/máquina) para este ejercicio:`, actual);
    if (nuevo !== null) {
        const n = parseFloat(nuevo.replace(',', '.'));
        if (!isNaN(n)) {
            setPesoBase(ejercicioId, n);
            // Actualizar todos los inputs de este ejercicio
            const card = btn.closest('.cyber-ejercicio-card');
            card.querySelectorAll('.weight-input').forEach(input => actualizarPesoPorLado(input));
        }
    }
};

function initWeightPerSideCalculation() {
    document.querySelectorAll('input.weight-input').forEach(input => {
        input.addEventListener('input', function () {
            actualizarPesoPorLado(this);
        });
        input.addEventListener('change', function () {
            actualizarPesoPorLado(this);
        });
        // Llamar una vez al cargar para mostrar el valor inicial
        actualizarPesoPorLado(input);
    });
}

// Ejecutar cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWeightPerSideCalculation);
} else {
    initWeightPerSideCalculation();
}

// ========================================================
// CRONÓMETRO DE DESCANSO SIMPLE
// ========================================================
let timerIntervals = new Map();

function toggleSimpleTimer(button) {
    const interval = timerIntervals.get(button);

    if (interval) {
        // Si está corriendo, reiniciar
        clearInterval(interval);
        timerIntervals.delete(button);
        button.textContent = '--:--';
        button.style.color = '#475569';
        button.style.fontWeight = '400';
    } else {
        // Iniciar desde cero
        let seconds = 0;
        button.textContent = '00:00';
        button.style.color = '#d4a847';
        button.style.fontWeight = '700';

        const newInterval = setInterval(() => {
            seconds++;
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            button.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        }, 1000);

        timerIntervals.set(button, newInterval);
    }
}

// ── BLOQUEAR TECLADO EN MÓVIL ──────────────────────────────
// Todos los inputs numéricos del entrenamiento se controlan
// con botones +/−, el teclado nunca debería aparecer.
document.addEventListener('DOMContentLoaded', function () {
    // Poner readonly en todos los inputs de peso, reps y RPE
    const inputsNoTeclado = document.querySelectorAll(
        'input.weight-input, input.reps-input, input.rpe-input'
    );

    inputsNoTeclado.forEach(function (input) {
        input.setAttribute('readonly', true);
        // Evitar que el click abra teclado
        input.addEventListener('focus', function () {
            this.blur();
        });
        // Evitar que el touchstart abra teclado
        input.addEventListener('touchstart', function (e) {
            e.preventDefault();
            this.blur();
        }, {passive: false});
    });

    // También bloquear el checkbox de "Hecho" que a veces
    // provoca scroll y reposicionamiento que abre teclado
    document.querySelectorAll('.cyber-form-check-input').forEach(function (cb) {
        cb.addEventListener('touchstart', function () {
            // Asegurar que ningún input tiene foco antes de marcar
            if (document.activeElement && document.activeElement !== document.body) {
                document.activeElement.blur();
            }
        });
    });
});