document.addEventListener('DOMContentLoaded', function () {
    const chartDataElement = document.getElementById('acwr-data');
    if (!chartDataElement) return;

    let chartData = JSON.parse(chartDataElement.textContent);

    // El backend ahora devuelve una lista de diccionarios,
    // JSON.parse(textContent) ya nos da el objeto correcto.

    const ctx = document.getElementById('acwrChart');

    if (ctx && chartData.length > 0) {
        // Gradient for Acute Load (Fatiga)
        const gradientAudit = ctx.getContext('2d').createLinearGradient(0, 0, 0, 400);
        gradientAudit.addColorStop(0, 'rgba(245, 158, 11, 0.5)'); // Amber
        gradientAudit.addColorStop(1, 'rgba(245, 158, 11, 0.0)');

        // Gradient for Chronic Load (Fitness)
        const gradientChronic = ctx.getContext('2d').createLinearGradient(0, 0, 0, 400);
        gradientChronic.addColorStop(0, 'rgba(59, 130, 246, 0.5)'); // Blue
        gradientChronic.addColorStop(1, 'rgba(59, 130, 246, 0.0)');

        new Chart(ctx, {
            type: 'line',
    data: {
        datasets: [{
                        label: 'Carga Aguda (Fatiga)',
                        data: chartData.map(d => d.carga_aguda),
                        borderColor: '#C8AA6E', // Amber-500
                        backgroundColor: gradientAudit,
                        yAxisID: 'y',
                        tension: 0.4,
                        fill: true,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    },
                    {
                        label: 'Carga Crónica (Fitness)',
                        data: chartData.map(d => d.carga_cronica),
                        borderColor: '#3b82f6', // Blue-500
                        backgroundColor: gradientChronic,
                        yAxisID: 'y',
                        tension: 0.4,
                        fill: true,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    },
                    {
                        label: 'Ratio ACWR',
                        data: chartData.map(d => d.acwr),
                        backgroundColor: (context) => {
                            const value = context.raw;
                            if (value >= 1.5) return 'rgba(239, 68, 68, 0.5)'; // Red
                            if (value >= 1.3) return 'rgba(245, 158, 11, 0.5)'; // Amber
                            if (value < 0.8) return 'rgba(59, 130, 246, 0.5)'; // Blue
                            return 'rgba(16, 185, 129, 0.5)'; // Emerald (Optimal)
                        },
                        borderColor: (context) => {
                            const value = context.raw;
                            if (value >= 1.5) return '#ef4444';
                            if (value >= 1.3) return '#f59e0b';
                            if (value < 0.8) return '#3b82f6';
                            return '#10b981';
                        },
                        borderWidth: 1,
                        yAxisID: 'y1',
                        type: 'bar',
                        barPercentage: 0.5
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
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'week', tooltipFormat: 'dd MMM yyyy' },
                        /* ticks from defaults */,
                        grid: { display: false }
                    },
                    y: {
                        position: 'left',
                        /* ticks from defaults */,
                        /* grid from defaults */,
                        title: { display: true, text: 'Carga (UA)', color: '#cbd5e1' }
                    },
                    y1: {
                        position: 'right',
                        /* ticks from defaults */,
                        grid: { display: false },
                        title: { display: true, text: 'Ratio ACWR', color: '#cbd5e1' },
                        min: 0,
                        suggestedMax: 2.0
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: '#f8fafc', usePointStyle: true, boxWidth: 6 }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(200,170,110,0.08)',
                        titleColor: '#f8fafc',
                        bodyColor: '#cbd5e1',
                        borderColor: '#334155',
                        borderWidth: 1,
                        padding: 10,
                        displayColors: true,
                        callbacks: {
                            label: function (context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += context.parsed.y.toFixed(2);
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    }
});

