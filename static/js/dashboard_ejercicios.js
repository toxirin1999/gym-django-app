/**
 * dashboard_ejercicios.js (VERSIÓN FINAL)
 * JavaScript para el dashboard de análisis de ejercicios
 * Solución con event delegation y datos embebidos
 */

let graficoProgresionActual = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log('=== Dashboard de Ejercicios Iniciado ===');

    // Inicializar gráfico de volumen mensual
    initVolumenMensualChart();

    // Configurar event listeners para los botones de gráfico
    setupGraficoButtons();

    // Configurar cierre del modal
    setupModalClose();
});

/**
 * Inicializa el gráfico de volumen mensual
 */
function initVolumenMensualChart() {
    const ctx = document.getElementById('volumenMensualChart');

    if (!ctx) {
        console.warn('Canvas volumenMensualChart no encontrado');
        return;
    }

    if (!window.dashboardData) {
        console.warn('No hay datos del dashboard');
        return;
    }

    const { volumenMensualLabels, volumenMensualData } = window.dashboardData;

    if (!volumenMensualLabels || volumenMensualLabels.length === 0) {
        console.warn('No hay datos de volumen mensual');
        return;
    }

    new Chart(ctx, {
        type: 'bar',
    data: {
        datasets: [{
                label: 'Volumen (kg)',
                data: volumenMensualData,
                backgroundColor: 'rgba(200,170,110,0.2)',
                borderColor: 'rgba(200,170,110,0.5)',
                borderWidth: 2,
                borderRadius: 8,
                hoverBackgroundColor: 'rgba(6, 182, 212, 0.8)',
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#06b6d4',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            return 'Volumen: ' + context.parsed.y.toLocaleString() + ' kg';
                        }
                    }
                }
            },
            scales: {
                x: {
                    /* ticks from defaults */
                    },
                    /* grid from defaults */
                },
                y: {
                    beginAtZero: true,
                    /* ticks from defaults */
                    },
                    /* grid from defaults */
                }
            }
        }
    });

    console.log('✓ Gráfico de volumen mensual creado');
}

/**
 * Configura los event listeners para los botones de gráfico
 * Usa event delegation para manejar todos los botones
 */
function setupGraficoButtons() {
    // Buscar todos los botones de gráfico
    const botones = document.querySelectorAll('.btn-grafico');

    console.log(`Encontrados ${botones.length} botones de gráfico`);

    botones.forEach(function(boton) {
        boton.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();

            console.log('=== Click en botón de gráfico ===');

            // Obtener el ID del ejercicio desde el atributo data
            const ejercicioId = this.getAttribute('data-ejercicio-id');
            const ejercicioNombre = this.getAttribute('data-ejercicio-nombre');

            console.log('Ejercicio ID:', ejercicioId);
            console.log('Ejercicio Nombre:', ejercicioNombre);

            // Buscar el script con los datos JSON
            const scriptElement = document.getElementById('data-' + ejercicioId);

            if (!scriptElement) {
                console.error('No se encontró el elemento de datos:', 'data-' + ejercicioId);
                alert('Error: No se encontraron los datos del ejercicio');
                return;
            }

            try {
                // Parsear el JSON
                const historial = JSON.parse(scriptElement.textContent);
                console.log('Historial parseado:', historial);

                if (!historial || historial.length === 0) {
                    alert('No hay datos suficientes para mostrar el gráfico');
                    return;
                }

                // Abrir el modal con los datos
                abrirModalEjercicio(ejercicioNombre, historial);

            } catch (error) {
                console.error('Error al parsear JSON:', error);
                console.error('Contenido del script:', scriptElement.textContent);
                alert('Error al cargar los datos del ejercicio');
            }
        });
    });
}

/**
 * Abre el modal con los datos del ejercicio
 * @param {string} nombre - Nombre del ejercicio
 * @param {Array} historial - Array con el historial del ejercicio
 */
function abrirModalEjercicio(nombre, historial) {
    console.log('=== Abriendo modal ===');
    console.log('Nombre:', nombre);
    console.log('Registros:', historial.length);

    // Actualizar título del modal
    document.getElementById('modalTitulo').textContent = nombre;

    // Calcular estadísticas
    const registros = historial.length;
    const pesos = historial.map(h => parseFloat(h.peso) || 0);
    const pesoPromedio = pesos.reduce((sum, peso) => sum + peso, 0) / registros;

    // Actualizar estadísticas en el modal
    document.getElementById('modalRegistros').textContent = registros;
    document.getElementById('modalPesoPromedio').textContent = pesoPromedio.toFixed(1) + ' kg';

    // Crear gráfico de progresión
    crearGraficoProgresion(historial);

    // Mostrar modal
    const modal = document.getElementById('modalDetalleEjercicio');
    modal.style.display = 'flex';

    // Prevenir scroll del body
    document.body.style.overflow = 'hidden';

    console.log('✓ Modal abierto correctamente');
}

/**
 * Crea el gráfico de progresión de un ejercicio
 * @param {Array} historial - Array con el historial del ejercicio
 */
function crearGraficoProgresion(historial) {
    const ctx = document.getElementById('graficoProgresion');

    if (!ctx) {
        console.error('Canvas graficoProgresion no encontrado');
        return;
    }

    // Destruir gráfico anterior si existe
    if (graficoProgresionActual) {
        graficoProgresionActual.destroy();
        console.log('Gráfico anterior destruido');
    }

    // Preparar datos
    const fechas = historial.map(h => {
        const fecha = new Date(h.fecha);
        return fecha.toLocaleDateString('es-ES', { day: '2-digit', month: 'short' });
    });

    const pesos = historial.map(h => parseFloat(h.peso) || 0);
    const volumenes = historial.map(h => parseFloat(h.volumen) || 0);
    // Phase 15: RPE and Recovery Load
    const rpes = historial.map(h => h.rpe ? parseFloat(h.rpe) : null);
    const recoveryLoads = historial.map(h => h.is_recovery_load);

    console.log('Datos del gráfico:');
    console.log('- Fechas:', fechas.length);
    console.log('- Pesos:', pesos);
    console.log('- Volúmenes:', volumenes);
    console.log('- RPEs:', rpes);

    // Crear nuevo gráfico
    graficoProgresionActual = new Chart(ctx, {
        type: 'line',
    data: {
        datasets: [{
                    label: 'Peso (kg)',
                    data: pesos,
                    borderColor: '#C8AA6E',
                    backgroundColor: 'rgba(200,170,110,0.08)',
                    borderWidth: 3,
                    tension: 0.3,
                    fill: true,
                    pointRadius: 5,
                    pointHoverRadius: 7,
                    pointBackgroundColor: '#06b6d4',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    yAxisID: 'y'
                },
                {
                    label: 'Volumen (kg)',
                    data: volumenes,
                    borderColor: '#a855f7',
                    backgroundColor: 'rgba(168, 85, 247, 0.1)',
                    borderWidth: 3,
                    tension: 0.3,
                    fill: true,
                    pointRadius: 5,
                    pointHoverRadius: 7,
                    pointBackgroundColor: '#a855f7',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    yAxisID: 'y1'
                },
                // Phase 15: RPE Line
                {
                    label: 'RPE',
                    data: rpes,
                    borderColor: '#f59e0b', // Amber
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: false,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    pointBackgroundColor: '#f59e0b',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    borderDash: [5, 5], // Dashed line to differentiate
                    yAxisID: 'y2',
                    spanGaps: true // Connect across null values
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
                            size: 13
                        },
                        padding: 15,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.9)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#06b6d4',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        afterLabel: function(context) {
                            const index = context.dataIndex;
                            const registro = historial[index];
                            const lineas = [
                                `Series: ${registro.series}`,
                                `Reps: ${registro.repeticiones}`
                            ];
                            if (registro.is_recovery_load) {
                                lineas.push(`⚠️ Carga de Transición`);
                            }
                            // Only add RPE line directly if the hovered point is not the RPE dataset itself
                            // (since standard tooltips already show the value for the active dataset)
                            if (context.dataset.label !== 'RPE' && registro.rpe) {
                                lineas.push(`RPE: ${registro.rpe}`);
                            }
                            return lineas;
                        }
                    }
                }
            },
            scales: {
                x: {
                    /* ticks from defaults */
                    },
                    /* grid from defaults */
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Peso (kg)',
                        color: '#06b6d4',
                        font: {
                            size: 12,
                            weight: 'bold'
                        }
                    },
                    /* ticks from defaults */
                    },
                    /* grid from defaults */
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Volumen (kg)',
                        color: '#a855f7',
                        font: {
                            size: 12,
                            weight: 'bold'
                        }
                    },
                    /* ticks from defaults */
                    },
                    grid: {
                        drawOnChartArea: false,
                        drawBorder: false
                    }
                },
                y2: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'RPE',
                        color: '#f59e0b',
                        font: {
                            size: 12,
                            weight: 'bold'
                        }
                    },
                    min: 0,
                    max: 10,
                    /* ticks from defaults */,
                    grid: {
                        drawOnChartArea: false,
                        drawBorder: false
                    }
                }
            }
        }
    });

    console.log('✓ Gráfico de progresión creado');
}

/**
 * Configura los event listeners para cerrar el modal
 */
function setupModalClose() {
    const modal = document.getElementById('modalDetalleEjercicio');

    if (!modal) {
        console.warn('Modal no encontrado');
        return;
    }

    // Cerrar al hacer clic en el fondo
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            cerrarModal();
        }
    });

    // Cerrar con tecla Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.style.display === 'flex') {
            cerrarModal();
        }
    });

    console.log('✓ Event listeners del modal configurados');
}

/**
 * Cierra el modal de detalle de ejercicio
 */
function cerrarModal() {
    console.log('Cerrando modal');

    const modal = document.getElementById('modalDetalleEjercicio');
    modal.style.display = 'none';

    // Restaurar scroll del body
    document.body.style.overflow = 'auto';

    // Destruir gráfico para liberar memoria
    if (graficoProgresionActual) {
        graficoProgresionActual.destroy();
        graficoProgresionActual = null;
        console.log('✓ Gráfico destruido');
    }
}
