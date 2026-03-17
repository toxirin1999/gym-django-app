
document.addEventListener('DOMContentLoaded', function () {
    initChart();
});

let chartInstance = null;
let allData = []; // Store full dataset locally for filtering

function initChart() {
    const dataElement = document.getElementById('progresion-data');
    if (!dataElement) return;

    try {
        allData = JSON.parse(dataElement.textContent);
    } catch (e) {
        console.error("Error parsing progresion data:", e);
        return;
    }

    // Initial render with all data
    renderChart(allData);
}

function renderChart(data) {
    const canvas = document.getElementById('progressChart');
    const mensaje = document.getElementById('noDataMessage');

    if (!canvas || !mensaje) return;

    if (chartInstance) {
        chartInstance.destroy();
    }

    if (data && data.some(d => d.peso > 0 || d.volumen > 0)) {
        canvas.style.display = 'block';
        mensaje.style.display = 'none';

        const ctx = canvas.getContext('2d');

        chartInstance = new Chart(ctx, {
            type: 'line',
    data: {
        datasets: [{
                    label: 'Peso (kg)',
                    data: data.map(d => d.peso),
                    borderColor: '#C8AA6E',
                    backgroundColor: 'rgba(200,170,110,0.08)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4
                }, {
                    label: '1RM Est. (kg)',
                    data: data.map(d => d.rm || null), // Handle missing rm
                    borderColor: '#f59e0b', // Warning color (Orange/Gold)
                    backgroundColor: 'rgba(245, 158, 11, 0.0)',
                    borderWidth: 2,
                    borderDash: [5, 5], // Dotted line
                    fill: false,
                    tension: 0.4,
                    pointRadius: 0, // Cleaner look
                    pointHoverRadius: 4
                }, {
                    label: 'Volumen (kg)',
                    data: data.map(d => d.volumen),
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    yAxisID: 'y1',
                    hidden: true // Hide volume by default to avoid clutter? Or keep visible. 
                    // User didnt ask to hide it, so keeping it visible but maybe cleaner.
                }]
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
                        labels: { color: '#f8fafc', font: { family: "'Inter', sans-serif" } }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(30, 41, 59, 0.9)',
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
                                    label += context.parsed.y + ' kg';
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: { display: true, text: 'Peso / 1RM (kg)', color: '#cbd5e1' },
                        /* ticks from defaults */ },
                        /* grid from defaults */
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: 'Volumen (kg)', color: '#cbd5e1' },
                        /* ticks from defaults */ },
                        grid: { drawOnChartArea: false }
                    },
                    x: {
                        /* ticks from defaults */ },
                        /* grid from defaults */
                    }
                }
            }
        });
    } else {
        canvas.style.display = 'none';
        mensaje.style.display = 'block';
    }
}

// Filter Function
window.filterChart = function (months, btnElement) {
    // 1. Update UI active state
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    btnElement.classList.add('active');

    // 2. Filter data
    if (months === 'all') {
        renderChart(allData);
        return;
    }

    const cutoffDate = new Date();
    cutoffDate.setMonth(cutoffDate.getMonth() - months);

    const filteredData = allData.filter(d => {
        const date = new Date(d.fecha);
        return date >= cutoffDate;
    });

    renderChart(filteredData);
};

// Global function to be called from HTML onchange
window.cambiarEjercicio = function () {
    const select = document.getElementById('ejercicio-select');
    const ejercicio = select.value;

    if (ejercicio) {
        showLoading();
        window.location.href = `?ejercicio=${encodeURIComponent(ejercicio)}`;
    }
};

function showLoading() {
    // Create loading overlay if it doesn't exist
    let overlay = document.querySelector('.loading-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.innerHTML = '<div class="spinner"></div>';
        document.body.appendChild(overlay);
    }

    // Slight delay to allow DOM update
    requestAnimationFrame(() => {
        overlay.classList.add('active');
    });
}
