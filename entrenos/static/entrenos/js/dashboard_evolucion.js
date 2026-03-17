/**
 * Dashboard de Evolución - JavaScript Premium
 * Gráficos con gradientes neón, animaciones suaves y efectos visuales avanzados
 */

document.addEventListener("DOMContentLoaded", function () {

    // ============================================================
    // CONFIGURACIÓN DE COLORES PREMIUM NEÓN
    // ============================================================
    const colors = {
        // Colores neón principales
        cyan: '#00d4ff',
        magenta: '#ff00d4',
        purple: '#a855f7',
        orange: '#ff9f43',
        yellow: '#fbbf24',
        green: '#22c55e',
        lime: '#84cc16',
        red: '#ef4444',
        pink: '#ec4899',
        blue: '#3b82f6',

        // Textos
        textPrimary: '#ffffff',
        textSecondary: 'rgba(255, 255, 255, 0.6)',
        textMuted: 'rgba(255, 255, 255, 0.35)',

        // Grids y fondos
        gridColor: 'rgba(255, 255, 255, 0.04)',
        bgCard: 'rgba(15, 23, 42, 0.6)'
    };

    // Paleta de colores para gráficos (orden específico para máximo contraste)
    const chartPalette = [
        colors.cyan,
        colors.magenta,
        colors.orange,
        colors.green,
        colors.purple,
        colors.yellow,
        colors.pink,
        colors.blue,
        colors.lime,
        colors.red
    ];

    // ============================================================
    // UTILIDADES PARA GRADIENTES
    // ============================================================
    function hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result
            ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`
            : '255, 255, 255';
    }

    function createVerticalGradient(ctx, color1, color2, opacityStart = 0.6, opacityEnd = 0) {
        const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
        gradient.addColorStop(0, `rgba(${hexToRgb(color1)}, ${opacityStart})`);
        gradient.addColorStop(0.5, `rgba(${hexToRgb(color2 || color1)}, ${opacityStart * 0.3})`);
        gradient.addColorStop(1, `rgba(${hexToRgb(color2 || color1)}, ${opacityEnd})`);
        return gradient;
    }

    function createHorizontalGradient(ctx, color1, color2) {
        const gradient = ctx.createLinearGradient(0, 0, ctx.canvas.width, 0);
        gradient.addColorStop(0, color1);
        gradient.addColorStop(1, color2);
        return gradient;
    }

    // ============================================================
    // CONFIGURACIÓN GLOBAL DE CHART.JS
    // ============================================================
    Chart.defaults.font.family = "'Inter', -apple-system, sans-serif";
    Chart.defaults.color = colors.textSecondary;
    Chart.defaults.borderColor = colors.gridColor;

    // Plugin para fondo con gradiente sutil
    const backgroundPlugin = {
        id: 'customCanvasBackgroundColor',
        beforeDraw: (chart) => {
            const ctx = chart.canvas.getContext('2d');
            ctx.save();
            ctx.globalCompositeOperation = 'destination-over';
            ctx.fillStyle = 'transparent';
            ctx.fillRect(0, 0, chart.width, chart.height);
            ctx.restore();
        }
    };

    // ============================================================
    // GRÁFICO DE VOLUMEN SEMANAL (Multidimensional: Volumen + RPE + Fases)
    // ============================================================
    const volumenCtx = document.getElementById('volumenSemanalChart');
    if (volumenCtx) {
        const ctx = volumenCtx.getContext('2d');
        const volumenLabels = JSON.parse(volumenCtx.dataset.volumenLabels || '[]');
        const volumenData = JSON.parse(volumenCtx.dataset.volumenData || '[]');
        const rpeData = JSON.parse(volumenCtx.dataset.volumenRpe || '[]');
        const fasesData = JSON.parse(volumenCtx.dataset.volumenFases || '[]');

        const areaGradient = createVerticalGradient(ctx, colors.cyan, colors.purple, 0.4, 0);
        const lineGradient = createHorizontalGradient(ctx, colors.cyan, colors.purple);

        new Chart(volumenCtx, {
            type: 'line',
    data: {
        datasets: [{
                        label: 'Volumen (kg)',
                        data: volumenData,
                        borderColor: lineGradient,
                        borderWidth: 3,
                        pointBackgroundColor: colors.cyan,
                        pointBorderColor: '#0a0f19',
                        pointBorderWidth: 2,
                        pointRadius: 5,
                        fill: true,
                        backgroundColor: areaGradient,
                        tension: 0.4,
                        yAxisID: 'y',
                    },
                    {
                        label: 'Intensidad (RPE)',
                        data: rpeData,
                        borderColor: colors.magenta,
                        borderWidth: 2,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                        tension: 0.4,
                        yAxisID: 'yRpe',
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        align: 'end',
                        labels: { boxWidth: 12, font: { size: 11 } }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(200,170,110,0.08)',
                        titleColor: colors.textPrimary,
                        borderColor: colors.cyan,
                        borderWidth: 1,
                        cornerRadius: 12,
                        padding: 14,
                        callbacks: {
                            label: (context) => {
                                if (context.datasetIndex === 0) return `Volumen: ${context.parsed.y.toLocaleString()} kg`;
                                return `RPE Medio: ${context.parsed.y.toFixed(1)}`;
                            },
                            afterBody: (context) => {
                                const index = context[0].dataIndex;
                                return `Fase: ${fasesData[index].toUpperCase()}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        /* grid from defaults */,
                        ticks: { font: { size: 10 }, callback: (value) => value.toLocaleString() }
                    },
                    yRpe: {
                        position: 'right',
                        min: 0,
                        max: 10,
                        grid: { display: false },
                        ticks: { font: { size: 10 }, color: colors.magenta }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { font: { size: 10 } }
                    }
                }
            },
            plugins: [backgroundPlugin, {
                id: 'phaseBackground',
                beforeDraw: (chart) => {
                    const { ctx, chartArea: { top, bottom, left, right }, scales: { x } } = chart;
                    const width = x.getPixelForValue(1) - x.getPixelForValue(0);

                    fasesData.forEach((fase, i) => {
                        const xPos = x.getPixelForValue(i) - width / 2;
                        let color = 'transparent';
                        if (fase === 'volumen') color = 'rgba(0, 212, 255, 0.03)';
                        if (fase === 'definicion') color = 'rgba(255, 0, 212, 0.03)';

                        ctx.fillStyle = color;
                        ctx.fillRect(xPos, top, width, bottom - top);
                    });
                }
            }]
        });
    }

    // ============================================================
    // DISTRIBUCIÓN MUSCULAR (Doughnut con gradientes)
    // ============================================================
    const distribucionCtx = document.getElementById('distribucionMuscularChart');
    if (distribucionCtx) {
        const distribucionLabels = JSON.parse(distribucionCtx.dataset.distribucionLabels || '[]');
        const distribucionData = JSON.parse(distribucionCtx.dataset.distribucionData || '[]');

        new Chart(distribucionCtx, {
            type: 'doughnut',
            data: {
                labels: distribucionLabels,
                datasets: [{
                    data: distribucionData,
                    backgroundColor: chartPalette.slice(0, distribucionData.length),
                    borderWidth: 0,
                    hoverOffset: 15,
                    hoverBorderWidth: 3,
                    hoverBorderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '72%',
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            boxWidth: 14,
                            boxHeight: 14,
                            padding: 16,
                            font: { size: 12, weight: '500' },
                            usePointStyle: true,
                            pointStyle: 'circle'
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(10, 15, 25, 0.95)',
                        titleColor: colors.textPrimary,
                        bodyColor: colors.textSecondary,
                        borderColor: '#C8AA6E',
                        borderWidth: 1,
                        cornerRadius: 12,
                        padding: 14,
                        callbacks: {
                            label: (context) => {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return `${context.label}: ${percentage}%`;
                            }
                        }
                    }
                },
                animation: {
                    animateRotate: true,
                    animateScale: true,
                    duration: 1200,
                    easing: 'easeOutQuart'
                }
            }
        });
    }

    // ============================================================
    // GRÁFICO ACWR (Línea con zonas de riesgo)
    // ============================================================
    const acwrCtx = document.getElementById('acwrChart');
    if (acwrCtx) {
        const ctx = acwrCtx.getContext('2d');
        const acwrData = JSON.parse(acwrCtx.dataset.acwr || '[]');

        if (acwrData.length > 0) {
            // Plugin para dibujar zonas de fondo
            const zonePlugin = {
                id: 'zoneBackground',
                beforeDraw: (chart) => {
                    const ctx = chart.ctx;
                    const yAxis = chart.scales.y;
                    const xAxis = chart.scales.x;

                    // Zona óptima (0.8 - 1.3)
                    const y1 = yAxis.getPixelForValue(1.3);
                    const y2 = yAxis.getPixelForValue(0.8);

                    ctx.save();
                    ctx.fillStyle = 'rgba(34, 197, 94, 0.08)';
                    ctx.fillRect(xAxis.left, y1, xAxis.width, y2 - y1);
                    ctx.restore();
                }
            };

            const lineGradient = createHorizontalGradient(ctx, colors.cyan, colors.purple);

            new Chart(acwrCtx, {
                type: 'line',
    data: {
        datasets: [{
                        label: 'ACWR',
                        data: acwrData.map(d => d.acwr),
                        borderColor: lineGradient,
                        borderWidth: 3,
                        pointRadius: 0,
                        pointHoverRadius: 6,
                        pointHoverBackgroundColor: colors.cyan,
                        tension: 0.4,
                        fill: false
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: 'rgba(200,170,110,0.08)',
                            borderColor: colors.cyan,
                            borderWidth: 1,
                            cornerRadius: 10,
                            padding: 12,
                            callbacks: {
                                label: (context) => `Ratio: ${context.parsed.y.toFixed(2)}`
                            }
                        }
                    },
                    scales: {
                        y: {
                            position: 'right',
                            min: 0.4,
                            max: 2.0,
                            /* grid from defaults */,
                            ticks: {
                                stepSize: 0.4,
                                font: { size: 10 }
                            }
                        },
                        x: {
                            display: false
                        }
                    },
                    animation: {
                        duration: 1200,
                        easing: 'easeOutQuart'
                    }
                },
                plugins: [zonePlugin]
            });

            // Actualizar aguja del gauge
            const lastAcwr = acwrData[acwrData.length - 1].acwr;
            const needle = document.getElementById('gaugeNeedle');
            if (needle) {
                // Mapear ACWR (0-2) a ángulo (180° - 0°)
                const clampedAcwr = Math.min(2, Math.max(0, lastAcwr));
                const angle = 180 - (clampedAcwr * 90);
                const rad = angle * Math.PI / 180;
                const needleLength = 38;

                needle.setAttribute('x2', (60 + needleLength * Math.cos(rad)).toFixed(1));
                needle.setAttribute('y2', (55 - needleLength * Math.sin(rad)).toFixed(1));
            }
        }
    }

    // ============================================================
    // RADAR DE EQUILIBRIO MUSCULAR
    // ============================================================
    const radarCtx = document.getElementById('balanceRadarChart');
    if (radarCtx) {
        const radarData = JSON.parse(radarCtx.dataset.radar || '{}');

        if (radarData.labels && radarData.valores) {
            new Chart(radarCtx, {
                type: 'radar',
    data: {
        datasets: [{
                        data: radarData.valores,
                        backgroundColor: 'rgba(200,170,110,0.1)',
                        borderColor: colors.cyan,
                        borderWidth: 3,
                        pointRadius: 5,
                        pointBackgroundColor: colors.cyan,
                        pointBorderColor: '#0a0f19',
                        pointBorderWidth: 2,
                        pointHoverRadius: 8,
                        pointHoverBackgroundColor: '#fff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: 'rgba(10, 15, 25, 0.95)',
                            borderColor: colors.cyan,
                            borderWidth: 1,
                            cornerRadius: 10,
                            padding: 12
                        }
                    },
                    scales: {
                        r: {
                            /* grid from defaults */,
                            angleLines: {
                                color: colors.gridColor
                            },
                            pointLabels: {
                                font: { size: 11, weight: '600' },
                                color: colors.textSecondary
                            },
                            ticks: {
                                display: false,
                                stepSize: 0.5
                            },
                            suggestedMin: 0,
                            suggestedMax: 1.5
                        }
                    },
                    animation: {
                        duration: 1500,
                        easing: 'easeOutQuart'
                    }
                }
            });
        }
    }

    // ============================================================
    // GRÁFICO DE INTENSIDAD (Polar Area)
    // ============================================================
    const intensidadCtx = document.getElementById('intensidadChart');
    if (intensidadCtx) {
        const intensidadData = JSON.parse(intensidadCtx.dataset.intensidad || '{}');

        if (intensidadData.labels && intensidadData.data) {
            const polarColors = [
                'rgba(0, 212, 255, 0.7)',
                'rgba(168, 85, 247, 0.7)',
                'rgba(255, 159, 67, 0.7)',
                'rgba(239, 68, 68, 0.7)'
            ];

            new Chart(intensidadCtx, {
                type: 'polarArea',
                data: {
                    labels: intensidadData.labels,
                    datasets: [{
                        data: intensidadData.data,
                        backgroundColor: polarColors,
                        borderWidth: 2,
                        borderColor: '#C8AA6E'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: {
                                boxWidth: 14,
                                padding: 16,
                                font: { size: 11, weight: '500' },
                                usePointStyle: true
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(10, 15, 25, 0.95)',
                            borderColor: 'rgba(255, 255, 255, 0.1)',
                            borderWidth: 1,
                            cornerRadius: 10,
                            padding: 12
                        }
                    },
                    scales: {
                        r: {
                            /* grid from defaults */,
                            ticks: { display: false }
                        }
                    },
                    animation: {
                        animateRotate: true,
                        animateScale: true,
                        duration: 1200
                    }
                }
            });
        }
    }

    // ============================================================
    // GRÁFICO DE VOLUMEN ÓPTIMO (Barras con gradiente)
    // ============================================================
    const volOptimoCtx = document.getElementById('volumenOptimoChart');
    if (volOptimoCtx) {
        const ctx = volOptimoCtx.getContext('2d');
        const volOptimoData = JSON.parse(volOptimoCtx.dataset.volOptimo || '{}');

        if (volOptimoData.labels && volOptimoData.series_reales) {
            // Generar array de recomendados si no existe
            const recommendedValue = volOptimoData.min_recomendado || 10;
            const recommendedData = volOptimoData.series_recomendadas || new Array(volOptimoData.labels.length).fill(recommendedValue);

            // Gradientes premium
            const realGradient = ctx.createLinearGradient(0, 0, 0, 400);
            realGradient.addColorStop(0, colors.yellow);
            realGradient.addColorStop(1, 'rgba(251, 191, 36, 0.3)');

            const targetGradient = ctx.createLinearGradient(0, 0, 0, 400);
            targetGradient.addColorStop(0, colors.magenta);
            targetGradient.addColorStop(1, 'rgba(255, 0, 212, 0.3)');

            new Chart(volOptimoCtx, {
                type: 'bar',
    data: {
        datasets: [{
                            label: 'Completado',
                            data: volOptimoData.series_reales,
                            backgroundColor: realGradient,
                            borderRadius: 6,
                            borderSkipped: false,
                            barThickness: 12,
                            hoverBackgroundColor: colors.yellow
                        },
                        {
                            label: 'Recomendado (Mín)',
                            data: recommendedData,
                            backgroundColor: targetGradient,
                            borderRadius: 6,
                            borderSkipped: false,
                            barThickness: 12,
                            hoverBackgroundColor: colors.magenta
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top',
                            align: 'end',
                            labels: {
                                boxWidth: 10,
                                boxHeight: 10,
                                usePointStyle: true,
                                pointStyle: 'circle',
                                font: { size: 11, weight: '600' },
                                padding: 20
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(200,170,110,0.2)',
                            borderColor: colors.cyan,
                            borderWidth: 1,
                            cornerRadius: 10,
                            padding: 12,
                            mode: 'index',
                            intersect: false,
                            callbacks: {
                                label: (context) => `${context.dataset.label}: ${context.parsed.y} series`
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            /* grid from defaults */,
                            ticks: {
                                padding: 10,
                                font: { size: 11 }
                            }
                        },
                        x: {
                            grid: { display: false },
                            ticks: {
                                padding: 10,
                                font: { size: 11 },
                                maxRotation: 0
                            }
                        }
                    },
                    animation: {
                        duration: 1500,
                        easing: 'easeOutQuart'
                    }
                }
            });
        }
    }

    // ============================================================
    // HEATMAP DE ACTIVIDAD ANUAL
    // ============================================================
    const heatmapContainer = document.getElementById('heatmap');
    if (heatmapContainer) {
        const activityData = JSON.parse(heatmapContainer.dataset.actividad || '{}');
        const today = new Date();
        const year = today.getFullYear();

        // Calcular el primer día del año (ajustado al lunes)
        const startDate = new Date(year, 0, 1);
        const dayOfWeek = startDate.getDay();
        startDate.setDate(startDate.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1));

        // Crear celdas del heatmap
        const fragment = document.createDocumentFragment();

        for (let i = 0; i < 371; i++) {
            const date = new Date(startDate);
            date.setDate(startDate.getDate() + i);
            const dateString = date.toISOString().split('T')[0];

            const dayDiv = document.createElement('div');
            dayDiv.classList.add('heatmap-day');

            if (date.getFullYear() === year) {
                const level = activityData[dateString] || 0;
                if (level > 0) {
                    dayDiv.dataset.level = Math.min(level, 4);
                    dayDiv.title = `${dateString}: ${level} entrenamiento${level > 1 ? 's' : ''}`;
                }
            } else {
                dayDiv.style.opacity = '0.15';
            }

            fragment.appendChild(dayDiv);
        }

        heatmapContainer.appendChild(fragment);
    }

    // ============================================================
    // ANIMACIÓN DE CONTEO PARA STAT VALUES
    // ============================================================
    function animateCount(element, target, duration = 1500) {
        const start = 0;
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Easing function (ease out quad)
            const easeProgress = 1 - (1 - progress) * (1 - progress);

            const current = Math.floor(start + (target - start) * easeProgress);
            element.textContent = current.toLocaleString();

            if (progress < 1) {
                requestAnimationFrame(update);
            } else {
                // Restaurar el valor original con formato
                const originalText = element.dataset.count;
                if (originalText && originalText.includes('%')) {
                    element.textContent = originalText;
                }
            }
        }

        requestAnimationFrame(update);
    }

    // Aplicar animación a los stat values cuando sean visibles
    const statValues = document.querySelectorAll('.stat-value[data-count]');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const element = entry.target;
                const targetValue = parseInt(element.dataset.count) || 0;
                animateCount(element, targetValue);
                observer.unobserve(element);
            }
        });
    }, { threshold: 0.5 });

    statValues.forEach(el => observer.observe(el));

    // ============================================================
    // EFECTO HOVER EN CARDS (Glow dinámico)
    // ============================================================
    const cards = document.querySelectorAll('.card');

    cards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            card.style.setProperty('--mouse-x', `${x}px`);
            card.style.setProperty('--mouse-y', `${y}px`);
        });
    });

    // ============================================================
    // ANIMACIÓN DE BARRAS DE PROGRESO
    // ============================================================
    const progressBars = document.querySelectorAll('.progress-bar');

    const progressObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const bar = entry.target;
                const width = bar.style.width;
                bar.style.width = '0%';

                setTimeout(() => {
                    bar.style.width = width;
                }, 100);

                progressObserver.unobserve(bar);
            }
        });
    }, { threshold: 0.3 });

    progressBars.forEach(bar => progressObserver.observe(bar));

    // ============================================================
    // SMOOTH SCROLL PARA NAVEGACIÓN INTERNA
    // ============================================================
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    console.log('✨ Dashboard Premium cargado correctamente');
});