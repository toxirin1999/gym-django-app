// Configuración de gráficas con Chart.js
document.addEventListener('DOMContentLoaded', function() {
    const clienteId = document.currentScript.getAttribute('data-cliente-id') || "{{ cliente.id }}";
    const colores = {
        pesos: 'rgba(54, 162, 235, 0.8)',
        grasas: 'rgba(255, 99, 132, 0.8)',
        cinturas: 'rgba(75, 192, 192, 0.8)',
        pechos: 'rgba(255, 159, 64, 0.8)',
        biceps: 'rgba(153, 102, 255, 0.8)',
        muslos: 'rgba(210, 180, 140, 0.8)'
    };

    let chart = null;

    function construirURL(clienteId) {
        const inicio = document.getElementById('fechaInicio').value;
        const fin = document.getElementById('fechaFin').value;
        let url = `/clientes/datos-graficas/${clienteId}/`;
        if (inicio && fin) url += `?start=${inicio}&end=${fin}`;
        return url;
    }

    function cargarGrafica() {
        fetch(construirURL(clienteId))
            .then(response => response.json())
            .then(data => {
                const ctx = document.getElementById('graficaProgreso').getContext('2d');
                const seleccionadas = Array.from(document.getElementById('medidasSelect').selectedOptions)
                                          .map(opt => opt.value);

                const datasets = seleccionadas.map(key => ({
                    label: key.charAt(0).toUpperCase() + key.slice(1),
                    data: data[key],
                    borderColor: colores[key],
                    backgroundColor: colores[key].replace('0.8', '0.2'),
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true
                }));

                if (!chart) {
                    chart = new Chart(ctx, {
                        type: 'line',
                        data: { labels: data.fechas, datasets },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: {
                                    position: 'bottom',
                                    onClick: (e, legendItem, legend) => {
                                        const index = legendItem.datasetIndex;
                                        const meta = chart.getDatasetMeta(index);
                                        meta.hidden = !meta.hidden;
                                        chart.update();
                                    }
                                },
                                tooltip: { mode: 'index', intersect: false }
                            },
                            hover: { mode: 'nearest', intersect: true },
                            scales: { y: { beginAtZero: false } }
                        }
                    });
                } else {
                    chart.data.labels = data.fechas;
                    chart.data.datasets = datasets;
                    chart.update();
                }
            });
    }

    // Event listeners
    document.getElementById('medidasSelect').addEventListener('change', cargarGrafica);
    document.getElementById('filtrarFechas').addEventListener('click', cargarGrafica);

    // Exportar datos
    document.getElementById('exportarDatos').addEventListener('click', function() {
        fetch(construirURL(clienteId))
            .then(response => response.json())
            .then(data => {
                let csvContent = "data:text/csv;charset=utf-8,";
                csvContent += "Fecha," + Object.keys(colores).join(",") + "\n";

                data.fechas.forEach((fecha, i) => {
                    const row = [fecha];
                    Object.keys(colores).forEach(key => {
                        row.push(data[key][i] || '');
                    });
                    csvContent += row.join(",") + "\n";
                });

                const encodedUri = encodeURI(csvContent);
                const link = document.createElement("a");
                link.setAttribute("href", encodedUri);
                link.setAttribute("download", `datos_${clienteId}.csv`);
                document.body.appendChild(link);
                link.click();
            });
    });

    // Carga inicial
    cargarGrafica();
});