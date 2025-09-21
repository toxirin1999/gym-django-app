// static/js/notificaciones.js
document.addEventListener('DOMContentLoaded', function() {
    // Elementos del DOM
    const notifDropdown = document.getElementById('notificaciones-dropdown');
    const notifContainer = document.querySelector('.notificaciones-container');
    const notifCount = document.querySelector('.notif-count');
    const notifEmpty = document.querySelector('.notif-empty');

    // Cliente ID (debe ser proporcionado por la plantilla)
    const clienteId = document.body.dataset.clienteId;

    if (!clienteId || !notifDropdown) return;

    // Función para cargar notificaciones
    function cargarNotificaciones() {
        fetch(`/logros/api/notificaciones/${clienteId}/`)
            .then(response => response.json())
            .then(data => {
                const notificaciones = data.notificaciones;

                // Actualizar contador
                if (notificaciones.length > 0) {
                    notifCount.textContent = notificaciones.length;
                    notifCount.style.display = 'inline-block';
                    notifEmpty.style.display = 'none';
                } else {
                    notifCount.style.display = 'none';
                    notifEmpty.style.display = 'block';
                }

                // Limpiar contenedor
                const items = notifContainer.querySelectorAll('.notif-item');
                items.forEach(item => item.remove());

                // Añadir notificaciones
                notificaciones.forEach(notif => {
                    const item = document.createElement('a');
                    item.className = 'dropdown-item notif-item';
                    item.href = `/logros/notificaciones/marcar-leida/${notif.id}/`;

                    item.innerHTML = `
                        <div class="d-flex w-100 justify-content-between">
                            <strong>${notif.icono} ${notif.titulo}</strong>
                            <small>${notif.fecha}</small>
                        </div>
                        <small>${notif.mensaje}</small>
                    `;

                    notifContainer.insertBefore(item, notifEmpty);
                });
            })
            .catch(error => console.error('Error al cargar notificaciones:', error));
    }

    // Cargar notificaciones al inicio
    cargarNotificaciones();

    // Cargar notificaciones cada 60 segundos
    setInterval(cargarNotificaciones, 60000);

    // Cargar notificaciones al abrir el dropdown
    notifDropdown.addEventListener('show.bs.dropdown', cargarNotificaciones);
});