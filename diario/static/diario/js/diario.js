/**
 * DIARIO SIC PARVIS MAGNA - JavaScript Principal
 * Sistema de diario digital con efectos cyberpunk e interactividad avanzada
 */

class DiarioSicParvisMagna {
    constructor() {
        this.init();
        this.setupEventListeners();
        this.initAnimations();
        this.setupNotifications();
    }

    init() {
        console.log('🚀 Iniciando Diario Sic Parvis Magna...');
        this.setupCSRFToken();
        this.initTheme();
        this.setupKeyboardShortcuts();
    }

    setupCSRFToken() {
        // Configurar token CSRF para todas las peticiones AJAX
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        if (csrfToken) {
            this.csrfToken = csrfToken;
        }
    }

    initTheme() {
        // Aplicar tema cyberpunk dinámico
        document.documentElement.style.setProperty('--current-time', Date.now());
        this.updateTimeBasedEffects();
        setInterval(() => this.updateTimeBasedEffects(), 60000); // Actualizar cada minuto
    }

    updateTimeBasedEffects() {
        const hour = new Date().getHours();
        const root = document.documentElement;
        
        // Ajustar intensidad de efectos según la hora
        if (hour >= 22 || hour <= 6) {
            // Modo nocturno - efectos más intensos
            root.style.setProperty('--cyber-intensity', '1.2');
            root.style.setProperty('--glow-intensity', '0.8');
        } else if (hour >= 18) {
            // Tarde - efectos moderados
            root.style.setProperty('--cyber-intensity', '1.0');
            root.style.setProperty('--glow-intensity', '0.6');
        } else {
            // Día - efectos suaves
            root.style.setProperty('--cyber-intensity', '0.8');
            root.style.setProperty('--glow-intensity', '0.4');
        }
    }

    setupEventListeners() {
        // Event listeners globales
        document.addEventListener('DOMContentLoaded', () => this.onDOMReady());
        window.addEventListener('resize', () => this.onWindowResize());
        document.addEventListener('visibilitychange', () => this.onVisibilityChange());
    }

    onDOMReady() {
        this.initCards();
        this.initForms();
        this.initModals();
        this.initTooltips();
        this.initCounters();
        this.initCalendar();
    }

    onWindowResize() {
        // Reajustar elementos responsivos
        this.adjustResponsiveElements();
    }

    onVisibilityChange() {
        if (document.hidden) {
            // Pausar animaciones cuando la página no está visible
            this.pauseAnimations();
        } else {
            // Reanudar animaciones
            this.resumeAnimations();
        }
    }

    // ========================================
    // ANIMACIONES Y EFECTOS VISUALES
    // ========================================

    initAnimations() {
        this.setupScrollAnimations();
        this.setupHoverEffects();
        this.setupLoadingAnimations();
        this.setupParticleEffects();
    }

    setupScrollAnimations() {
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-fade-in');
                    entry.target.style.animationDelay = `${Math.random() * 0.5}s`;
                }
            });
        }, observerOptions);

        // Observar elementos que necesitan animación
        document.querySelectorAll('.cyber-card, .cyber-stat, .entrada-item, .habito-item').forEach(el => {
            observer.observe(el);
        });
    }

    setupHoverEffects() {
        // Efectos de hover avanzados para tarjetas
        document.querySelectorAll('.cyber-card').forEach(card => {
            card.addEventListener('mouseenter', (e) => this.onCardHover(e, true));
            card.addEventListener('mouseleave', (e) => this.onCardHover(e, false));
            card.addEventListener('mousemove', (e) => this.onCardMouseMove(e));
        });

        // Efectos para botones
        document.querySelectorAll('.cyber-btn').forEach(btn => {
            btn.addEventListener('mouseenter', (e) => this.onButtonHover(e, true));
            btn.addEventListener('mouseleave', (e) => this.onButtonHover(e, false));
        });
    }

    onCardHover(event, isEntering) {
        const card = event.currentTarget;
        if (isEntering) {
            card.style.transform = 'translateY(-8px) scale(1.02)';
            card.style.boxShadow = '0 0 40px rgba(0, 255, 255, 0.4)';
            this.createRippleEffect(card, event);
        } else {
            card.style.transform = 'translateY(0) scale(1)';
            card.style.boxShadow = '0 0 20px rgba(0, 255, 255, 0.3)';
        }
    }

    onCardMouseMove(event) {
        const card = event.currentTarget;
        const rect = card.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        
        // Efecto de seguimiento del mouse
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = (y - centerY) / 20;
        const rotateY = (centerX - x) / 20;
        
        card.style.transform = `translateY(-8px) scale(1.02) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    }

    onButtonHover(event, isEntering) {
        const btn = event.currentTarget;
        if (isEntering) {
            btn.style.transform = 'translateY(-3px) scale(1.05)';
            this.createButtonGlow(btn);
        } else {
            btn.style.transform = 'translateY(0) scale(1)';
        }
    }

    createRippleEffect(element, event) {
        const ripple = document.createElement('div');
        const rect = element.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = event.clientX - rect.left - size / 2;
        const y = event.clientY - rect.top - size / 2;
        
        ripple.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            left: ${x}px;
            top: ${y}px;
            background: radial-gradient(circle, rgba(0, 255, 255, 0.3) 0%, transparent 70%);
            border-radius: 50%;
            pointer-events: none;
            animation: ripple 0.8s ease-out forwards;
            z-index: 1;
        `;
        
        element.style.position = 'relative';
        element.appendChild(ripple);
        
        setTimeout(() => ripple.remove(), 800);
    }

    createButtonGlow(button) {
        const glow = document.createElement('div');
        glow.className = 'button-glow';
        glow.style.cssText = `
            position: absolute;
            top: -2px;
            left: -2px;
            right: -2px;
            bottom: -2px;
            background: linear-gradient(45deg, #00ffff, #ff00ff, #00ff00, #ffff00);
            border-radius: inherit;
            z-index: -1;
            opacity: 0.7;
            filter: blur(8px);
            animation: buttonGlow 2s ease-in-out infinite;
        `;
        
        button.style.position = 'relative';
        button.appendChild(glow);
        
        setTimeout(() => glow.remove(), 2000);
    }

    setupLoadingAnimations() {
        // Animaciones de carga para elementos dinámicos
        this.createLoadingSpinner();
    }

    createLoadingSpinner() {
        const spinner = document.createElement('div');
        spinner.id = 'cyber-loading-spinner';
        spinner.innerHTML = `
            <div class="cyber-spinner">
                <div class="cyber-spinner-ring"></div>
                <div class="cyber-spinner-ring"></div>
                <div class="cyber-spinner-ring"></div>
                <div class="cyber-spinner-text">CARGANDO...</div>
            </div>
        `;
        spinner.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        `;
        document.body.appendChild(spinner);
    }

    showLoading() {
        document.getElementById('cyber-loading-spinner').style.display = 'flex';
    }

    hideLoading() {
        document.getElementById('cyber-loading-spinner').style.display = 'none';
    }

    setupParticleEffects() {
        // Crear sistema de partículas de fondo
        this.createParticleSystem();
    }

    createParticleSystem() {
        const canvas = document.createElement('canvas');
        canvas.id = 'particle-canvas';
        canvas.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: -1;
            opacity: 0.3;
        `;
        document.body.appendChild(canvas);
        
        this.initParticles(canvas);
    }

    initParticles(canvas) {
        const ctx = canvas.getContext('2d');
        const particles = [];
        const particleCount = 50;
        
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        
        // Crear partículas
        for (let i = 0; i < particleCount; i++) {
            particles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: (Math.random() - 0.5) * 0.5,
                size: Math.random() * 2 + 1,
                opacity: Math.random() * 0.5 + 0.2,
                color: ['#00ffff', '#ff00ff', '#00ff00'][Math.floor(Math.random() * 3)]
            });
        }
        
        // Animar partículas
        const animate = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            particles.forEach(particle => {
                particle.x += particle.vx;
                particle.y += particle.vy;
                
                // Rebotar en los bordes
                if (particle.x < 0 || particle.x > canvas.width) particle.vx *= -1;
                if (particle.y < 0 || particle.y > canvas.height) particle.vy *= -1;
                
                // Dibujar partícula
                ctx.beginPath();
                ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
                ctx.fillStyle = particle.color;
                ctx.globalAlpha = particle.opacity;
                ctx.fill();
            });
            
            requestAnimationFrame(animate);
        };
        
        animate();
        
        // Redimensionar canvas
        window.addEventListener('resize', () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        });
    }

    // ========================================
    // FUNCIONALIDADES INTERACTIVAS
    // ========================================

    initCards() {
        // Inicializar funcionalidades específicas de tarjetas
        this.setupCardExpansion();
        this.setupCardFiltering();
        this.setupCardSorting();
    }

    setupCardExpansion() {
        document.querySelectorAll('[data-expandable]').forEach(card => {
            const header = card.querySelector('.cyber-card-header');
            if (header) {
                header.style.cursor = 'pointer';
                header.addEventListener('click', () => this.toggleCardExpansion(card));
            }
        });
    }

    toggleCardExpansion(card) {
        const body = card.querySelector('.cyber-card-body');
        const isExpanded = card.classList.contains('expanded');
        
        if (isExpanded) {
            body.style.maxHeight = '0';
            body.style.opacity = '0';
            card.classList.remove('expanded');
        } else {
            body.style.maxHeight = body.scrollHeight + 'px';
            body.style.opacity = '1';
            card.classList.add('expanded');
        }
    }

    setupCardFiltering() {
        const filterButtons = document.querySelectorAll('[data-filter]');
        filterButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const filter = e.target.dataset.filter;
                this.filterCards(filter);
                this.updateActiveFilter(e.target);
            });
        });
    }

    filterCards(filter) {
        const cards = document.querySelectorAll('[data-category]');
        cards.forEach(card => {
            const category = card.dataset.category;
            if (filter === 'all' || category === filter) {
                card.style.display = 'block';
                card.classList.add('animate-fade-in');
            } else {
                card.style.display = 'none';
            }
        });
    }

    updateActiveFilter(activeButton) {
        document.querySelectorAll('[data-filter]').forEach(btn => {
            btn.classList.remove('active');
        });
        activeButton.classList.add('active');
    }

    setupCardSorting() {
        const sortSelect = document.querySelector('[data-sort]');
        if (sortSelect) {
            sortSelect.addEventListener('change', (e) => {
                this.sortCards(e.target.value);
            });
        }
    }

    sortCards(sortBy) {
        const container = document.querySelector('[data-sortable-container]');
        if (!container) return;
        
        const cards = Array.from(container.querySelectorAll('[data-sortable]'));
        
        cards.sort((a, b) => {
            const aValue = a.dataset[sortBy] || a.textContent;
            const bValue = b.dataset[sortBy] || b.textContent;
            
            if (sortBy === 'date') {
                return new Date(bValue) - new Date(aValue);
            }
            
            return aValue.localeCompare(bValue);
        });
        
        // Reordenar elementos
        cards.forEach(card => container.appendChild(card));
        
        // Animar reordenación
        cards.forEach((card, index) => {
            card.style.animationDelay = `${index * 0.1}s`;
            card.classList.add('animate-fade-in');
        });
    }

    initForms() {
        // Mejorar formularios con validación y efectos
        this.setupFormValidation();
        this.setupFormEffects();
        this.setupAutoSave();
    }

    setupFormValidation() {
        const forms = document.querySelectorAll('form[data-validate]');
        forms.forEach(form => {
            form.addEventListener('submit', (e) => this.validateForm(e));
            
            // Validación en tiempo real
            const inputs = form.querySelectorAll('input, textarea, select');
            inputs.forEach(input => {
                input.addEventListener('blur', () => this.validateField(input));
                input.addEventListener('input', () => this.clearFieldError(input));
            });
        });
    }

    validateForm(event) {
        const form = event.target;
        const inputs = form.querySelectorAll('[required]');
        let isValid = true;
        
        inputs.forEach(input => {
            if (!this.validateField(input)) {
                isValid = false;
            }
        });
        
        if (!isValid) {
            event.preventDefault();
            this.showNotification('Por favor, completa todos los campos requeridos', 'error');
        }
    }

    validateField(field) {
        const value = field.value.trim();
        const isRequired = field.hasAttribute('required');
        const type = field.type;
        
        // Limpiar errores previos
        this.clearFieldError(field);
        
        // Validar campo requerido
        if (isRequired && !value) {
            this.showFieldError(field, 'Este campo es requerido');
            return false;
        }
        
        // Validaciones específicas por tipo
        if (value) {
            switch (type) {
                case 'email':
                    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
                        this.showFieldError(field, 'Ingresa un email válido');
                        return false;
                    }
                    break;
                case 'url':
                    if (!/^https?:\/\/.+/.test(value)) {
                        this.showFieldError(field, 'Ingresa una URL válida');
                        return false;
                    }
                    break;
                case 'number':
                    if (isNaN(value)) {
                        this.showFieldError(field, 'Ingresa un número válido');
                        return false;
                    }
                    break;
            }
        }
        
        return true;
    }

    showFieldError(field, message) {
        field.classList.add('error');
        
        let errorElement = field.parentNode.querySelector('.field-error');
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.className = 'field-error';
            field.parentNode.appendChild(errorElement);
        }
        
        errorElement.textContent = message;
        errorElement.style.cssText = `
            color: #ff0040;
            font-size: 0.8rem;
            margin-top: 0.25rem;
            animation: shake 0.5s ease-in-out;
        `;
    }

    clearFieldError(field) {
        field.classList.remove('error');
        const errorElement = field.parentNode.querySelector('.field-error');
        if (errorElement) {
            errorElement.remove();
        }
    }

    setupFormEffects() {
        // Efectos visuales para formularios
        const inputs = document.querySelectorAll('.cyber-form-control');
        inputs.forEach(input => {
            input.addEventListener('focus', (e) => this.onInputFocus(e, true));
            input.addEventListener('blur', (e) => this.onInputFocus(e, false));
        });
    }

    onInputFocus(event, isFocused) {
        const input = event.target;
        const label = input.parentNode.querySelector('.cyber-form-label');
        
        if (isFocused) {
            input.style.boxShadow = '0 0 20px rgba(0, 255, 255, 0.5)';
            if (label) {
                label.style.color = '#00ffff';
                label.style.textShadow = '0 0 10px rgba(0, 255, 255, 0.5)';
            }
        } else {
            input.style.boxShadow = '0 0 15px rgba(0, 255, 255, 0.4)';
            if (label) {
                label.style.color = '#4dd0e1';
                label.style.textShadow = '0 0 5px rgba(0, 255, 255, 0.3)';
            }
        }
    }

    setupAutoSave() {
        // Auto-guardado para formularios largos
        const autoSaveForms = document.querySelectorAll('[data-autosave]');
        autoSaveForms.forEach(form => {
            const inputs = form.querySelectorAll('input, textarea, select');
            inputs.forEach(input => {
                input.addEventListener('input', () => {
                    clearTimeout(this.autoSaveTimeout);
                    this.autoSaveTimeout = setTimeout(() => {
                        this.autoSaveForm(form);
                    }, 2000);
                });
            });
        });
    }

    autoSaveForm(form) {
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        
        // Guardar en localStorage
        const formId = form.id || 'autosave-form';
        localStorage.setItem(`autosave-${formId}`, JSON.stringify(data));
        
        // Mostrar indicador de guardado
        this.showAutoSaveIndicator();
    }

    showAutoSaveIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'autosave-indicator';
        indicator.innerHTML = '<i class="fas fa-save"></i> Guardado automáticamente';
        indicator.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(0, 255, 0, 0.9);
            color: #000;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            z-index: 9999;
            animation: fadeInOut 3s ease-in-out forwards;
        `;
        
        document.body.appendChild(indicator);
        setTimeout(() => indicator.remove(), 3000);
    }

    // ========================================
    // SISTEMA DE NOTIFICACIONES
    // ========================================

    setupNotifications() {
        this.notificationContainer = this.createNotificationContainer();
    }

    createNotificationContainer() {
        const container = document.createElement('div');
        container.id = 'notification-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            max-width: 400px;
        `;
        document.body.appendChild(container);
        return container;
    }

    showNotification(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        const id = 'notification-' + Date.now();
        
        const colors = {
            success: '#00ff00',
            error: '#ff0040',
            warning: '#ffff00',
            info: '#00ffff'
        };
        
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-triangle',
            warning: 'fas fa-exclamation-circle',
            info: 'fas fa-info-circle'
        };
        
        notification.id = id;
        notification.className = 'cyber-notification';
        notification.innerHTML = `
            <div class="notification-content">
                <i class="${icons[type]}"></i>
                <span class="notification-message">${message}</span>
                <button class="notification-close" onclick="diario.closeNotification('${id}')">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        notification.style.cssText = `
            background: rgba(0, 0, 0, 0.9);
            border: 2px solid ${colors[type]};
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 0 20px ${colors[type]}40;
            animation: slideInRight 0.5s ease-out;
            backdrop-filter: blur(10px);
        `;
        
        this.notificationContainer.appendChild(notification);
        
        // Auto-cerrar
        if (duration > 0) {
            setTimeout(() => this.closeNotification(id), duration);
        }
        
        return id;
    }

    closeNotification(id) {
        const notification = document.getElementById(id);
        if (notification) {
            notification.style.animation = 'slideOutRight 0.5s ease-out forwards';
            setTimeout(() => notification.remove(), 500);
        }
    }

    // ========================================
    // FUNCIONALIDADES ESPECÍFICAS DEL DIARIO
    // ========================================

    initCounters() {
        // Animación de contadores numéricos
        const counters = document.querySelectorAll('.cyber-stat-value');
        const observerOptions = {
            threshold: 0.5
        };
        
        const counterObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.animateCounter(entry.target);
                    counterObserver.unobserve(entry.target);
                }
            });
        }, observerOptions);
        
        counters.forEach(counter => {
            counterObserver.observe(counter);
        });
    }

    animateCounter(element) {
        const target = parseInt(element.textContent) || 0;
        const duration = 2000;
        const step = target / (duration / 16);
        let current = 0;
        
        const timer = setInterval(() => {
            current += step;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            element.textContent = Math.floor(current);
        }, 16);
    }

    initCalendar() {
        // Inicializar calendario si existe
        const calendarElement = document.getElementById('calendar');
        if (calendarElement) {
            this.setupCalendar(calendarElement);
        }
    }

    setupCalendar(element) {
        // Configuración básica del calendario
        // Aquí se integraría con una librería de calendario como FullCalendar
        console.log('Inicializando calendario...');
    }

    initModals() {
        // Mejorar modales con efectos cyberpunk
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            modal.addEventListener('show.bs.modal', (e) => this.onModalShow(e));
            modal.addEventListener('hide.bs.modal', (e) => this.onModalHide(e));
        });
    }

    onModalShow(event) {
        const modal = event.target;
        modal.style.backdropFilter = 'blur(10px)';
        
        // Efecto de aparición
        const modalDialog = modal.querySelector('.modal-dialog');
        if (modalDialog) {
            modalDialog.style.animation = 'modalSlideIn 0.5s ease-out';
        }
    }

    onModalHide(event) {
        const modal = event.target;
        const modalDialog = modal.querySelector('.modal-dialog');
        if (modalDialog) {
            modalDialog.style.animation = 'modalSlideOut 0.5s ease-out';
        }
    }

    initTooltips() {
        // Inicializar tooltips con efectos cyberpunk
        const tooltipElements = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        tooltipElements.forEach(element => {
            new bootstrap.Tooltip(element, {
                customClass: 'cyber-tooltip'
            });
        });
    }

    // ========================================
    // UTILIDADES Y HELPERS
    // ========================================

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K - Búsqueda rápida
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.openQuickSearch();
            }
            
            // Ctrl/Cmd + N - Nueva entrada
            if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
                e.preventDefault();
                this.openNewEntryModal();
            }
            
            // Escape - Cerrar modales/overlays
            if (e.key === 'Escape') {
                this.closeAllOverlays();
            }
        });
    }

    openQuickSearch() {
        // Implementar búsqueda rápida
        console.log('Abriendo búsqueda rápida...');
    }

    openNewEntryModal() {
        // Abrir modal para nueva entrada
        console.log('Abriendo modal de nueva entrada...');
    }

    closeAllOverlays() {
        // Cerrar todos los overlays abiertos
        const modals = document.querySelectorAll('.modal.show');
        modals.forEach(modal => {
            bootstrap.Modal.getInstance(modal)?.hide();
        });
    }

    adjustResponsiveElements() {
        // Ajustar elementos para diferentes tamaños de pantalla
        const isMobile = window.innerWidth < 768;
        
        if (isMobile) {
            document.body.classList.add('mobile-view');
            this.adjustMobileLayout();
        } else {
            document.body.classList.remove('mobile-view');
            this.adjustDesktopLayout();
        }
    }

    adjustMobileLayout() {
        // Ajustes específicos para móvil
        const cards = document.querySelectorAll('.cyber-card');
        cards.forEach(card => {
            card.style.margin = '0.5rem 0';
        });
    }

    adjustDesktopLayout() {
        // Ajustes específicos para escritorio
        const cards = document.querySelectorAll('.cyber-card');
        cards.forEach(card => {
            card.style.margin = '1rem 0';
        });
    }

    pauseAnimations() {
        document.body.classList.add('animations-paused');
    }

    resumeAnimations() {
        document.body.classList.remove('animations-paused');
    }

    // ========================================
    // API HELPERS
    // ========================================

    async makeRequest(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            }
        };
        
        const finalOptions = { ...defaultOptions, ...options };
        
        try {
            this.showLoading();
            const response = await fetch(url, finalOptions);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.hideLoading();
            return data;
        } catch (error) {
            this.hideLoading();
            this.showNotification(`Error: ${error.message}`, 'error');
            throw error;
        }
    }

    // ========================================
    // MÉTODOS PÚBLICOS PARA USO EN TEMPLATES
    // ========================================

    toggleHabito(habitoId, completado) {
        return this.makeRequest('/diario/prosoche/habito/toggle/', {
            method: 'POST',
            body: JSON.stringify({
                habito_id: habitoId,
                completado: completado
            })
        }).then(data => {
            if (data.success) {
                this.showNotification('Hábito actualizado correctamente', 'success');
            }
            return data;
        });
    }

    updateEudaimonia(areaId, data) {
        return this.makeRequest('/diario/eudaimonia/actualizar/', {
            method: 'POST',
            body: JSON.stringify({
                area_id: areaId,
                ...data
            })
        }).then(response => {
            if (response.success) {
                this.showNotification('Área actualizada correctamente', 'success');
            }
            return response;
        });
    }

    saveGnosisContent(data) {
        return this.makeRequest('/diario/gnosis/crear/', {
            method: 'POST',
            body: JSON.stringify(data)
        }).then(response => {
            if (response.success) {
                this.showNotification('Contenido guardado correctamente', 'success');
            }
            return response;
        });
    }
}

// Inicializar la aplicación cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    window.diario = new DiarioSicParvisMagna();
});

// Agregar estilos CSS adicionales para las animaciones
const additionalStyles = `
    @keyframes ripple {
        0% { transform: scale(0); opacity: 1; }
        100% { transform: scale(2); opacity: 0; }
    }
    
    @keyframes buttonGlow {
        0%, 100% { opacity: 0.7; }
        50% { opacity: 1; }
    }
    
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    @keyframes modalSlideIn {
        from { transform: translateY(-50px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
    }
    
    @keyframes modalSlideOut {
        from { transform: translateY(0); opacity: 1; }
        to { transform: translateY(-50px); opacity: 0; }
    }
    
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-5px); }
        75% { transform: translateX(5px); }
    }
    
    @keyframes fadeInOut {
        0% { opacity: 0; transform: translateY(-20px); }
        20%, 80% { opacity: 1; transform: translateY(0); }
        100% { opacity: 0; transform: translateY(-20px); }
    }
    
    .cyber-form-control.error {
        border-color: #ff0040 !important;
        box-shadow: 0 0 15px rgba(255, 0, 64, 0.4) !important;
    }
    
    .cyber-spinner {
        position: relative;
        width: 80px;
        height: 80px;
    }
    
    .cyber-spinner-ring {
        position: absolute;
        width: 100%;
        height: 100%;
        border: 3px solid transparent;
        border-top: 3px solid #00ffff;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    .cyber-spinner-ring:nth-child(2) {
        width: 60px;
        height: 60px;
        top: 10px;
        left: 10px;
        border-top-color: #ff00ff;
        animation-duration: 1.5s;
        animation-direction: reverse;
    }
    
    .cyber-spinner-ring:nth-child(3) {
        width: 40px;
        height: 40px;
        top: 20px;
        left: 20px;
        border-top-color: #00ff00;
        animation-duration: 2s;
    }
    
    .cyber-spinner-text {
        position: absolute;
        top: 100px;
        left: 50%;
        transform: translateX(-50%);
        color: #00ffff;
        font-family: 'Orbitron', monospace;
        font-size: 0.8rem;
        letter-spacing: 2px;
        animation: pulse 1s ease-in-out infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 0.5; }
        50% { opacity: 1; }
    }
    
    .animations-paused * {
        animation-play-state: paused !important;
    }
    
    .cyber-tooltip .tooltip-inner {
        background: rgba(0, 0, 0, 0.9);
        border: 1px solid #00ffff;
        color: #00ffff;
        font-family: 'Rajdhani', sans-serif;
        backdrop-filter: blur(10px);
    }
    
    .cyber-tooltip .tooltip-arrow::before {
        border-top-color: #00ffff;
    }
`;

// Inyectar estilos adicionales
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
document.head.appendChild(styleSheet);
