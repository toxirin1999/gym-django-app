/**
 * perfil_cliente.js
 * Script para la página de perfil del cliente
 * Maneja el gráfico de evolución y los acordeones del historial
 */

document.addEventListener('DOMContentLoaded', function() {
    // ==========================================
    // GRÁFICO DE EVOLUCIÓN
    // ==========================================
    initProgresoGrafico();

    // ==========================================
    // ACORDEONES DEL HISTORIAL
    // ==========================================
    initAcordeonesHistorial();
});

/**
 * Inicializa el gráfico de evolución de peso y grasa corporal
 */
function initProgresoGrafico() {
    const ctx = document.getElementById('progresoGrafico');
    
    // Verificar que el canvas existe y que hay datos disponibles
    if (!ctx || !window.perfilClienteData) {
        return;
    }

    const { labels, pesos, grasas } = window.perfilClienteData;

    // Verificar que hay suficientes datos para mostrar el gráfico
    if (!labels || labels.length === 0) {
        return;
    }

    new Chart(ctx, {
        type: 'line',
    data: {
        datasets: [{
                    label: 'Peso (kg)',
                    data: pesos,
                    borderColor: '#C8AA6E',
                    backgroundColor: 'rgba(200,170,110,0.08)',
                    tension: 0.3,
                    yAxisID: 'y',
                    fill: true
                },
                {
                    label: 'Grasa (%)',
                    data: grasas,
                    borderColor: '#34D399',
                    backgroundColor: 'rgba(52, 211, 153, 0.1)',
                    tension: 0.3,
                    yAxisID: 'y1',
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#ffffff',
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#31cff4',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    /* ticks from defaults */,
                    /* grid from defaults */
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Peso (kg)',
                        color: '#31cff4',
                        font: {
                            size: 12,
                            weight: 'bold'
                        }
                    },
                    /* ticks from defaults */,
                    /* grid from defaults */
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Grasa (%)',
                        color: '#34D399',
                        font: {
                            size: 12,
                            weight: 'bold'
                        }
                    },
                    /* ticks from defaults */,
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
}

/**
 * Inicializa los acordeones del historial de entrenamientos
 */
function initAcordeonesHistorial() {
    const headers = document.querySelectorAll('.semana-header');
    
    headers.forEach(header => {
        // Evento de clic
        header.addEventListener('click', () => {
            toggleAcordeon(header);
        });

        // Evento de teclado para accesibilidad (Enter y Espacio)
        header.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleAcordeon(header);
            }
        });
    });
}

/**
 * Alterna el estado de un acordeón (abierto/cerrado)
 * @param {HTMLElement} header - El elemento header del acordeón
 */
function toggleAcordeon(header) {
    const contenido = header.nextElementSibling;
    const icon = header.querySelector('.accordion-icon');
    const isExpanded = header.getAttribute('aria-expanded') === 'true';
    
    // Alternar visibilidad del contenido
    if (contenido.style.display === 'none' || contenido.style.display === '') {
        contenido.style.display = 'block';
        header.setAttribute('aria-expanded', 'true');
        if (icon) {
            icon.style.transform = 'rotate(180deg)';
        }
    } else {
        contenido.style.display = 'none';
        header.setAttribute('aria-expanded', 'false');
        if (icon) {
            icon.style.transform = 'rotate(0deg)';
        }
    }
}
