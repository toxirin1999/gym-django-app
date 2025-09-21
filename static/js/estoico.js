// Estoico App JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Inicializar componentes
    initializeTooltips();
    initializeAnimations();
    initializeNotifications();
    initializeProgressTracking();
    initializeAutoSave();
    
    console.log('Estoico App initialized successfully');
});

// Inicializar tooltips de Bootstrap
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Animaciones de entrada
function initializeAnimations() {
    // Observador de intersección para animaciones
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in-up');
            }
        });
    }, {
        threshold: 0.1
    });

    // Observar elementos con clase animate-on-scroll
    document.querySelectorAll('.animate-on-scroll').forEach(el => {
        observer.observe(el);
    });
}

// Sistema de notificaciones
function initializeNotifications() {
    // Verificar soporte para notificaciones
    if ('Notification' in window) {
        // Solicitar permiso si no se ha otorgado
        if (Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }
}

// Tracking de progreso
function initializeProgressTracking() {
    // Actualizar barras de progreso con animación
    document.querySelectorAll('.progress-bar').forEach(bar => {
        const width = bar.getAttribute('data-width') || bar.style.width;
        bar.style.width = '0%';
        
        setTimeout(() => {
            bar.style.width = width;
        }, 500);
    });
}

// Auto-save para formularios
function initializeAutoSave() {
    const forms = document.querySelectorAll('form[data-autosave]');
    
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input, textarea, select');
        let autoSaveTimer;
        
        inputs.forEach(input => {
            input.addEventListener('input', () => {
                clearTimeout(autoSaveTimer);
                autoSaveTimer = setTimeout(() => {
                    autoSaveForm(form);
                }, 30000); // Auto-save cada 30 segundos
            });
        });
    });
}

// Función de auto-save
function autoSaveForm(form) {
    const formData = new FormData(form);
    const url = form.getAttribute('data-autosave-url') || form.action;
    
    fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Borrador guardado automáticamente', 'success');
        }
    })
    .catch(error => {
        console.error('Error en auto-save:', error);
    });
}

// Sistema de toasts/notificaciones
function showToast(message, type = 'info', duration = 3000) {
    const toastContainer = getOrCreateToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="fas fa-${getIconForType(type)} me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                    data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: duration
    });
    
    bsToast.show();
    
    // Remover el toast del DOM después de que se oculte
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

// Obtener o crear contenedor de toasts
function getOrCreateToastContainer() {
    let container = document.getElementById('toast-container');
    
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1055';
        document.body.appendChild(container);
    }
    
    return container;
}

// Obtener icono según el tipo de mensaje
function getIconForType(type) {
    const icons = {
        'success': 'check-circle',
        'danger': 'exclamation-triangle',
        'warning': 'exclamation-circle',
        'info': 'info-circle',
        'primary': 'info-circle'
    };
    
    return icons[type] || 'info-circle';
}

// Funciones para el calendario
function initializeCalendar() {
    const calendarDays = document.querySelectorAll('.calendar-day');
    
    calendarDays.forEach(day => {
        day.addEventListener('click', function() {
            const dayNumber = this.getAttribute('data-day');
            if (dayNumber) {
                window.location.href = `/estoico/diario/${dayNumber}/`;
            }
        });
        
        // Tooltip con información del día
        const dayInfo = this.getAttribute('data-info');
        if (dayInfo) {
            this.setAttribute('data-bs-toggle', 'tooltip');
            this.setAttribute('title', dayInfo);
        }
    });
}

// Funciones para estadísticas y gráficos
function initializeCharts() {
    // Gráfico de progreso semanal
    const progressChart = document.getElementById('progress-chart');
    if (progressChart) {
        createProgressChart(progressChart);
    }
    
    // Gráfico de calificaciones
    const ratingsChart = document.getElementById('ratings-chart');
    if (ratingsChart) {
        createRatingsChart(ratingsChart);
    }
}

// Crear gráfico de progreso (usando Chart.js si está disponible)
function createProgressChart(canvas) {
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js no está disponible');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    const data = JSON.parse(canvas.getAttribute('data-chart-data') || '[]');
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.date),
            datasets: [{
                label: 'Días Activos',
                data: data.map(d => d.active ? 1 : 0),
                borderColor: '#2c3e50',
                backgroundColor: 'rgba(44, 62, 80, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1,
                    ticks: {
                        callback: function(value) {
                            return value === 1 ? 'Activo' : 'Inactivo';
                        }
                    }
                }
            }
        }
    });
}

// Validación de formularios
function validateReflectionForm(form) {
    const textarea = form.querySelector('textarea[name="reflexion_personal"]');
    const text = textarea.value.trim();
    
    if (text.length < 10) {
        showToast('La reflexión debe tener al menos 10 caracteres', 'warning');
        textarea.focus();
        return false;
    }
    
    if (text.length > 2000) {
        showToast('La reflexión es demasiado larga (máximo 2000 caracteres)', 'warning');
        textarea.focus();
        return false;
    }
    
    return true;
}

// Funciones de utilidad
function formatDate(date) {
    return new Intl.DateTimeFormat('es-ES', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    }).format(date);
}

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    
    if (minutes > 0) {
        return `${minutes}m ${remainingSeconds}s`;
    }
    return `${remainingSeconds}s`;
}

// Funciones para logros
function markAchievementAsSeen(achievementId) {
    fetch(`/estoico/logro/${achievementId}/visto/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const button = document.querySelector(`[data-logro-id="${achievementId}"]`);
            if (button) {
                button.style.display = 'none';
            }
            showToast('Logro marcado como visto', 'success');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Error al marcar el logro', 'danger');
    });
}

// Obtener token CSRF
function getCsrfToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    return token ? token.value : '';
}

// Funciones para el modo oscuro
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
}

function initializeDarkMode() {
    const darkMode = localStorage.getItem('darkMode') === 'true';
    if (darkMode) {
        document.body.classList.add('dark-mode');
    }
}

// Funciones para búsqueda
function initializeSearch() {
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            const query = this.querySelector('input[name="query"]').value.trim();
            if (query.length < 3) {
                e.preventDefault();
                showToast('La búsqueda debe tener al menos 3 caracteres', 'warning');
            }
        });
    }
}

// Funciones para exportación
function exportReflections() {
    showToast('Preparando exportación...', 'info');
    
    fetch('/estoico/exportar/', {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (response.ok) {
            return response.blob();
        }
        throw new Error('Error en la exportación');
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `reflexiones_estoicas_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showToast('Reflexiones exportadas exitosamente', 'success');
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Error al exportar las reflexiones', 'danger');
    });
}

// Event listeners globales
document.addEventListener('click', function(e) {
    // Marcar logros como vistos
    if (e.target.classList.contains('mark-seen') || e.target.closest('.mark-seen')) {
        const button = e.target.classList.contains('mark-seen') ? e.target : e.target.closest('.mark-seen');
        const achievementId = button.getAttribute('data-logro-id');
        if (achievementId) {
            markAchievementAsSeen(achievementId);
        }
    }
    
    // Exportar reflexiones
    if (e.target.id === 'export-reflections' || e.target.closest('#export-reflections')) {
        e.preventDefault();
        exportReflections();
    }
});

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    initializeDarkMode();
    initializeCalendar();
    initializeCharts();
    initializeSearch();
});

// Funciones para PWA (Progressive Web App)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/sw.js')
            .then(function(registration) {
                console.log('ServiceWorker registrado exitosamente');
            })
            .catch(function(error) {
                console.log('Error al registrar ServiceWorker:', error);
            });
    });
}

