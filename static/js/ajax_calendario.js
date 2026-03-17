// ========== JAVASCRIPT PARA CARGAR DATOS CON AJAX ==========

// Obtener el cliente_id del HTML (añade data-cliente-id al body o contenedor)
const clienteId = document.body.dataset.clienteId;

// Función para cargar entrenamientos de un mes completo
async function cargarEntrenamientosDelMes(año, mes) {
    try {
        const response = await fetch(
            `/entrenos/ajax/entrenamientos-mes/${clienteId}/?año=${año}&mes=${mes}`
        );
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            // Actualizar el calendario con los datos
            actualizarCalendario(data.entrenamientos);
        } else {
            console.error('Error:', data.error);
        }
    } catch (error) {
        console.error('Error al cargar entrenamientos:', error);
    }
}

// Función para cargar un entrenamiento específico de un día
async function cargarEntrenamientoDia(fecha) {
    try {
        const response = await fetch(
            `/entrenos/ajax/entrenamiento/${clienteId}/?fecha=${fecha}`
        );
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success && data.entrenamiento) {
            // Mostrar el entrenamiento en un modal o panel
            mostrarEntrenamientoDia(data.entrenamiento, data.fecha);
        } else {
            mostrarMensajeDescanso(data.fecha);
        }
    } catch (error) {
        console.error('Error al cargar entrenamiento:', error);
    }
}

// Función para actualizar el calendario con los datos
function actualizarCalendario(entrenamientos) {
    // Iterar sobre cada día del calendario
    document.querySelectorAll('[data-fecha]').forEach(elemento => {
        const fecha = elemento.dataset.fecha;
        const entrenamiento = entrenamientos[fecha];
        
        if (entrenamiento) {
            // Añadir clase CSS para mostrar que hay entrenamiento
            elemento.classList.add('tiene-entrenamiento');
            elemento.classList.add(entrenamiento.fase_css || 'fase-default');
            
            // Crear un badge con el nombre del entrenamiento
            const badge = document.createElement('div');
            badge.className = 'entrenamiento-badge';
            badge.textContent = entrenamiento.nombre_rutina.split(' - ')[0];
            badge.title = entrenamiento.nombre_rutina;
            elemento.appendChild(badge);
            
            // Añadir evento click para mostrar detalles
            elemento.addEventListener('click', () => cargarEntrenamientoDia(fecha));
        }
    });
}

// Función para mostrar el entrenamiento del día
function mostrarEntrenamientoDia(entrenamiento, fecha) {
    // Crear un modal o panel con los detalles
    const modal = document.getElementById('modal-entrenamiento') || crearModal();
    
    modal.innerHTML = `
        <div class="modal-content">
            <button class="modal-close" onclick="cerrarModal()">✕</button>
            <h2>${entrenamiento.nombre_rutina}</h2>
            <p class="fecha">${fecha}</p>
            
            <div class="entrenamiento-detalles">
                <h3>Ejercicios</h3>
                <ul>
                    ${entrenamiento.ejercicios.map(ej => `
                        <li>
                            <strong>${ej.nombre}</strong>
                            <span>${ej.series} × ${ej.repeticiones} @ ${ej.peso}kg</span>
                        </li>
                    `).join('')}
                </ul>
            </div>
            
            ${entrenamiento.notas ? `
                <div class="notas">
                    <h3>Notas</h3>
                    <p>${entrenamiento.notas}</p>
                </div>
            ` : ''}
        </div>
    `;
    
    modal.style.display = 'block';
}

// Función para mostrar mensaje de descanso
function mostrarMensajeDescanso(fecha) {
    const modal = document.getElementById('modal-entrenamiento') || crearModal();
    
    modal.innerHTML = `
        <div class="modal-content">
            <button class="modal-close" onclick="cerrarModal()">✕</button>
            <h2>Día de Descanso</h2>
            <p class="fecha">${fecha}</p>
            <p class="descanso-message">No hay entrenamiento programado para este día.</p>
        </div>
    `;
    
    modal.style.display = 'block';
}

// Función para crear el modal
function crearModal() {
    const modal = document.createElement('div');
    modal.id = 'modal-entrenamiento';
    modal.className = 'modal';
    document.body.appendChild(modal);
    return modal;
}

// Función para cerrar el modal
function cerrarModal() {
    const modal = document.getElementById('modal-entrenamiento');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Cargar entrenamientos cuando se cambia de mes
function cambiarMes(año, mes) {
    cargarEntrenamientosDelMes(año, mes);
}

// Cargar entrenamientos del mes actual al iniciar
document.addEventListener('DOMContentLoaded', () => {
    const año = document.body.dataset.año || new Date().getFullYear();
    const mes = document.body.dataset.mes || new Date().getMonth() + 1;
    cargarEntrenamientosDelMes(año, mes);
});

// ========== ESTILOS CSS PARA EL MODAL ==========
const styles = `
    .modal {
        display: none;
        position: fixed;
        z-index: 1000;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.5);
        animation: fadeIn 0.3s ease;
    }

    .modal-content {
        background-color: var(--card-bg, #1e293b);
        margin: 5% auto;
        padding: 2rem;
        border: 1px solid var(--border-color, #334155);
        border-radius: 1rem;
        width: 90%;
        max-width: 600px;
        max-height: 80vh;
        overflow-y: auto;
        color: var(--text-primary, #f8fafc);
    }

    .modal-close {
        float: right;
        font-size: 2rem;
        font-weight: bold;
        cursor: pointer;
        background: none;
        border: none;
        color: var(--text-secondary, #cbd5e1);
        transition: color 0.3s ease;
    }

    .modal-close:hover {
        color: var(--accent-color, #06b6d4);
    }

    .entrenamiento-badge {
        display: inline-block;
        background: linear-gradient(135deg, #3b82f6, #06b6d4);
        color: white;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.75rem;
        font-weight: 600;
        margin-top: 0.25rem;
    }

    .tiene-entrenamiento {
        background: rgba(59, 130, 246, 0.1);
        border: 2px solid var(--primary-color, #3b82f6);
    }

    .entrenamiento-detalles ul {
        list-style: none;
        padding: 0;
    }

    .entrenamiento-detalles li {
        padding: 0.75rem;
        border-bottom: 1px solid var(--border-color, #334155);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .entrenamiento-detalles li:last-child {
        border-bottom: none;
    }

    .entrenamiento-detalles strong {
        color: var(--accent-color, #06b6d4);
    }

    .descanso-message {
        text-align: center;
        color: var(--text-secondary, #cbd5e1);
        font-style: italic;
        padding: 2rem;
    }

    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
`;

// Inyectar estilos
const styleSheet = document.createElement('style');
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);
