/**
 * DASHBOARD LIFTIN MEJORADO - JAVASCRIPT
 * Versión: 2.0
 * Funcionalidades: Gráficos, Animaciones, Interactividad
 */

// ===================================
// CONFIGURACIÓN GLOBAL
// ===================================

const DashboardConfig = {
    // Configuración de animaciones
    animations: {
        duration: 800,
        easing: 'ease-in-out',
        stagger: 100
    },
    
    // Configuración de gráficos
    charts: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true,
                position: 'bottom'
            }
        }
    },
    
    // Configuración de notificaciones
    notifications: {
        duration: 5000,
        position: 'top-right'
    },
    
    // Colores del tema
    colors: {
        primary: '#667eea',
        secondary: '#f093fb',
        success: '#4ade80',
        warning: '#fbbf24',
        error: '#f87171',
        info: '#60a5fa',
        liftin: '#3b82f6',
        manual: '#10b981',
        calories: '#f59e0b'
    }
};

// ===================================
// UTILIDADES
// ===================================

class Utils {
    // Formatear números con animación
    static animateNumber(element, finalValue, duration = 2000) {
        const startValue = 0;
        const startTime = performance.now();
        
        function updateNumber(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Easing function (ease-out)
            const easeOut = 1 - Math.pow(1 - progress, 3);
            const currentValue = Math.floor(startValue + (finalValue - startValue) * easeOut);
            
            element.textContent = Utils.formatNumber(currentValue);
            
            if (progress < 1) {
                requestAnimationFrame(updateNumber);
            } else {
                element.textContent = Utils.formatNumber(finalValue);
            }
        }
        
        requestAnimationFrame(updateNumber);
    }
    
    // Formatear números con separadores
    static formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toLocaleString();
    }
    
    // Generar gradiente para gráficos
    static createGradient(ctx, color1, color2) {
        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, color1);
        gradient.addColorStop(1, color2);
        return gradient;
    }
    
    // Debounce function
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    // Throttle function
    static throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
    
    // Generar ID único
    static generateId() {
        return Math.random().toString(36).substr(2, 9);
    }
    
    // Calcular porcentaje
    static calculatePercentage(value, total) {
        if (total === 0) return 0;
        return Math.round((value / total) * 100);
    }
}

// ===================================
// SISTEMA DE NOTIFICACIONES
// ===================================

class NotificationSystem {
    constructor() {
        this.container = document.getElementById('notification-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'notification-container';
            document.body.appendChild(this.container);
        }
    }
    
    show(message, type = 'info', duration = 5000) {
        const notification = this.createNotification(message, type);
        this.container.appendChild(notification);
        
        // Animar entrada
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);
        
        // Auto-remover
        setTimeout(() => {
            this.remove(notification);
        }, duration);
        
        return notification;
    }
    
    createNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <div class="notification-header">
                <span class="notification-title">${this.getTitle(type)}</span>
                <button class="notification-close">&times;</button>
            </div>
            <div class="notification-content">${message}</div>
        `;
        
        // Event listener para cerrar
        notification.querySelector('.notification-close').addEventListener('click', () => {
            this.remove(notification);
        });
        
        return notification;
    }
    
    getTitle(type) {
        const titles = {
            success: '✅ Éxito',
            warning: '⚠️ Advertencia',
            error: '❌ Error',
            info: 'ℹ️ Información'
        };
        return titles[type] || 'Notificación';
    }
    
    remove(notification) {
        notification.style.animation = 'slideOut 0.3s ease-in forwards';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }
    
    success(message, duration) {
        return this.show(message, 'success', duration);
    }
    
    warning(message, duration) {
        return this.show(message, 'warning', duration);
    }
    
    error(message, duration) {
        return this.show(message, 'error', duration);
    }
    
    info(message, duration) {
        return this.show(message, 'info', duration);
    }
}

// ===================================
// SISTEMA DE GRÁFICOS
// ===================================

class ChartManager {
    constructor() {
        this.charts = {};
        this.defaultOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#667eea',
                    borderWidth: 1,
                    cornerRadius: 8,
                    displayColors: true
                }
            },
            animation: {
                duration: 1000,
                easing: 'easeInOutQuart'
            }
        };
    }
    
    createProgressChart(canvasId, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        
        const chartData = {
            labels: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun'],
            datasets: [{
                label: 'Entrenamientos Liftin',
                data: [2, 4, 3, 5, 4, data.entrenamientos || 1],
                borderColor: DashboardConfig.colors.liftin,
                backgroundColor: Utils.createGradient(ctx.getContext('2d'), 
                    DashboardConfig.colors.liftin + '40', 
                    DashboardConfig.colors.liftin + '10'),
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: DashboardConfig.colors.liftin,
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 6,
                pointHoverRadius: 8
            }, {
                label: 'Entrenamientos Manuales',
                data: [1, 2, 1, 3, 2, data.manual || 0],
                borderColor: DashboardConfig.colors.manual,
                backgroundColor: Utils.createGradient(ctx.getContext('2d'), 
                    DashboardConfig.colors.manual + '40', 
                    DashboardConfig.colors.manual + '10'),
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: DashboardConfig.colors.manual,
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 6,
                pointHoverRadius: 8
            }]
        };
        
        const options = {
            ...this.defaultOptions,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#64748b',
                        font: {
                            size: 12
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#64748b',
                        font: {
                            size: 12
                        }
                    }
                }
            },
            plugins: {
                ...this.defaultOptions.plugins,
                legend: {
                    ...this.defaultOptions.plugins.legend,
                    labels: {
                        ...this.defaultOptions.plugins.legend.labels,
                        color: '#1e293b'
                    }
                }
            }
        };
        
        this.charts[canvasId] = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: options
        });
        
        return this.charts[canvasId];
    }
    
    createDistributionChart(canvasId, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        
        const total = (data.entrenamientos || 0) + (data.manual || 0);
        if (total === 0) {
            // Mostrar gráfico vacío
            data.entrenamientos = 1;
            data.manual = 0;
        }
        
        const chartData = {
            labels: ['Liftin', 'Manual'],
            datasets: [{
                data: [data.entrenamientos || 0, data.manual || 0],
                backgroundColor: [
                    DashboardConfig.colors.liftin,
                    DashboardConfig.colors.manual
                ],
                borderColor: [
                    DashboardConfig.colors.liftin,
                    DashboardConfig.colors.manual
                ],
                borderWidth: 2,
                hoverOffset: 10
            }]
        };
        
        const options = {
            ...this.defaultOptions,
            cutout: '60%',
            plugins: {
                ...this.defaultOptions.plugins,
                legend: {
                    display: false // La leyenda está en el HTML
                },
                tooltip: {
                    ...this.defaultOptions.plugins.tooltip,
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed;
                            const percentage = Utils.calculatePercentage(value, total);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            },
            animation: {
                animateRotate: true,
                animateScale: true,
                duration: 1500
            }
        };
        
        this.charts[canvasId] = new Chart(ctx, {
            type: 'doughnut',
            data: chartData,
            options: options
        });
        
        return this.charts[canvasId];
    }
    
    updateChart(chartId, newData) {
        const chart = this.charts[chartId];
        if (!chart) return;
        
        chart.data = newData;
        chart.update('active');
    }
    
    destroyChart(chartId) {
        if (this.charts[chartId]) {
            this.charts[chartId].destroy();
            delete this.charts[chartId];
        }
    }
    
    destroyAllCharts() {
        Object.keys(this.charts).forEach(chartId => {
            this.destroyChart(chartId);
        });
    }
}

// ===================================
// ANIMACIONES Y EFECTOS
// ===================================

class AnimationManager {
    constructor() {
        this.observers = [];
        this.initIntersectionObserver();
    }
    
    initIntersectionObserver() {
        const options = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };
        
        this.observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.animateElement(entry.target);
                }
            });
        }, options);
    }
    
    observeElement(element) {
        this.observer.observe(element);
    }
    
    animateElement(element) {
        // Animar números
        const numberElements = element.querySelectorAll('[data-count]');
        numberElements.forEach(el => {
            const finalValue = parseInt(el.getAttribute('data-count'));
            Utils.animateNumber(el, finalValue);
        });
        
        // Animar barras de progreso
        const progressBars = element.querySelectorAll('.progress-fill, .nivel-fill, .progreso-fill');
        progressBars.forEach(bar => {
            const width = bar.style.width;
            bar.style.width = '0%';
            setTimeout(() => {
                bar.style.width = width;
            }, 200);
        });
        
        // Animar cards
        if (element.classList.contains('stat-card-modern') || 
            element.classList.contains('challenge-card-modern') ||
            element.classList.contains('insight-card')) {
            element.style.opacity = '0';
            element.style.transform = 'translateY(30px)';
            
            setTimeout(() => {
                element.style.transition = 'all 0.6s ease-out';
                element.style.opacity = '1';
                element.style.transform = 'translateY(0)';
            }, 100);
        }
    }
    
    animateCounters() {
        const counters = document.querySelectorAll('[data-count]');
        counters.forEach(counter => {
            const finalValue = parseInt(counter.getAttribute('data-count'));
            Utils.animateNumber(counter, finalValue);
        });
    }
    
    staggerAnimation(elements, delay = 100) {
        elements.forEach((element, index) => {
            setTimeout(() => {
                element.style.opacity = '1';
                element.style.transform = 'translateY(0)';
            }, index * delay);
        });
    }
}

// ===================================
// GESTIÓN DE FILTROS Y PERÍODOS
// ===================================

class FilterManager {
    constructor() {
        this.currentPeriod = 'week';
        this.currentMetric = 'entrenamientos';
        this.initEventListeners();
    }
    
    initEventListeners() {
        // Filtros de período
        document.querySelectorAll('.btn-period, .btn-chart-filter').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.handlePeriodChange(e.target);
            });
        });
        
        // Filtros de ranking
        document.querySelectorAll('.btn-ranking-filter').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.handleRankingFilter(e.target);
            });
        });
    }
    
    handlePeriodChange(button) {
        const period = button.getAttribute('data-period');
        if (!period) return;
        
        // Actualizar estado visual
        button.parentElement.querySelectorAll('.btn-period, .btn-chart-filter').forEach(btn => {
            btn.classList.remove('active');
        });
        button.classList.add('active');
        
        this.currentPeriod = period;
        this.updateDashboardData(period);
    }
    
    handleRankingFilter(button) {
        const metric = button.getAttribute('data-metric');
        if (!metric) return;
        
        // Actualizar estado visual
        button.parentElement.querySelectorAll('.btn-ranking-filter').forEach(btn => {
            btn.classList.remove('active');
        });
        button.classList.add('active');
        
        this.currentMetric = metric;
        this.updateRankingData(metric);
    }
    
    updateDashboardData(period) {
        // Simular actualización de datos basada en el período
        const mockData = this.getMockDataForPeriod(period);
        
        // Actualizar números en las cards
        this.updateStatCards(mockData);
        
        // Actualizar gráficos
        if (window.chartManager) {
            window.chartManager.updateChart('progressChart', mockData.chartData);
        }
        
        // Mostrar notificación
        if (window.notifications) {
            window.notifications.info(`Datos actualizados para: ${this.getPeriodLabel(period)}`);
        }
    }
    
    updateRankingData(metric) {
        // Simular actualización del ranking
        const mockRanking = this.getMockRankingData(metric);
        this.updateRankingDisplay(mockRanking);
        
        if (window.notifications) {
            window.notifications.info(`Ranking actualizado por: ${this.getMetricLabel(metric)}`);
        }
    }
    
    getMockDataForPeriod(period) {
        const multipliers = {
            week: 1,
            month: 4,
            year: 48
        };
        
        const multiplier = multipliers[period] || 1;
        
        return {
            entrenamientos: Math.floor(Math.random() * 10 * multiplier) + 1,
            manual: Math.floor(Math.random() * 5 * multiplier),
            calorias: Math.floor(Math.random() * 1000 * multiplier) + 200,
            volumen: Math.floor(Math.random() * 5000 * multiplier) + 1000
        };
    }
    
    getMockRankingData(metric) {
        // Generar datos de ranking simulados
        return [
            { name: 'Cliente 1', value: Math.floor(Math.random() * 100) + 50 },
            { name: 'Cliente 2', value: Math.floor(Math.random() * 80) + 40 },
            { name: 'Cliente 3', value: Math.floor(Math.random() * 60) + 30 }
        ];
    }
    
    updateStatCards(data) {
        // Actualizar las cards de estadísticas con animación
        Object.keys(data).forEach(key => {
            const element = document.querySelector(`[data-stat="${key}"] .stat-number-modern`);
            if (element) {
                Utils.animateNumber(element, data[key]);
            }
        });
    }
    
    updateRankingDisplay(rankingData) {
        // Actualizar la visualización del ranking
        // Esta función se puede expandir para actualizar el podio y la lista
        console.log('Actualizando ranking:', rankingData);
    }
    
    getPeriodLabel(period) {
        const labels = {
            week: 'Esta Semana',
            month: 'Este Mes',
            year: 'Este Año'
        };
        return labels[period] || period;
    }
    
    getMetricLabel(metric) {
        const labels = {
            entrenamientos: 'Entrenamientos',
            calorias: 'Calorías',
            volumen: 'Volumen'
        };
        return labels[metric] || metric;
    }
}

// ===================================
// GESTIÓN DE DESAFÍOS
// ===================================

class ChallengeManager {
    constructor() {
        this.challenges = [];
        this.initEventListeners();
    }
    
    initEventListeners() {
        document.querySelectorAll('.btn-challenge-details').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const challengeCard = e.target.closest('.challenge-card-modern');
                const challengeId = challengeCard.getAttribute('data-challenge-id');
                this.showChallengeDetails(challengeId);
            });
        });
    }
    
    showChallengeDetails(challengeId) {
        // Mostrar modal o expandir detalles del desafío
        if (window.notifications) {
            window.notifications.info(`Mostrando detalles del desafío ${challengeId}`);
        }
        
        // Aquí se puede implementar un modal o expandir la card
        console.log(`Mostrando detalles del desafío: ${challengeId}`);
    }
    
    updateChallengeProgress(challengeId, newProgress) {
        const challengeCard = document.querySelector(`[data-challenge-id="${challengeId}"]`);
        if (!challengeCard) return;
        
        const progressBar = challengeCard.querySelector('.progress-fill');
        const progressText = challengeCard.querySelector('.current');
        
        if (progressBar) {
            progressBar.style.width = `${newProgress.percentage}%`;
        }
        
        if (progressText) {
            progressText.textContent = newProgress.current;
        }
        
        // Verificar si el desafío se completó
        if (newProgress.percentage >= 100) {
            this.completeChallenge(challengeId);
        }
    }
    
    completeChallenge(challengeId) {
        const challengeCard = document.querySelector(`[data-challenge-id="${challengeId}"]`);
        if (!challengeCard) return;
        
        // Añadir clase de completado
        challengeCard.classList.add('completed');
        
        // Mostrar notificación de éxito
        if (window.notifications) {
            window.notifications.success('¡Desafío completado! 🎉 Has ganado puntos adicionales.');
        }
        
        // Animar la card
        challengeCard.style.transform = 'scale(1.05)';
        setTimeout(() => {
            challengeCard.style.transform = 'scale(1)';
        }, 300);
    }
}

// ===================================
// GESTIÓN DE INSIGHTS
// ===================================

class InsightManager {
    constructor() {
        this.insights = [];
        this.initEventListeners();
    }
    
    initEventListeners() {
        document.querySelectorAll('.btn-insight-action').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.handleInsightAction(e.target);
            });
        });
        
        const refreshBtn = document.querySelector('.btn-refresh-insights');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshInsights();
            });
        }
    }
    
    handleInsightAction(button) {
        const insightCard = button.closest('.insight-card');
        const actionText = button.textContent.trim();
        
        // Simular acción del insight
        button.textContent = 'Procesando...';
        button.disabled = true;
        
        setTimeout(() => {
            button.textContent = '✓ Aplicado';
            button.style.background = DashboardConfig.colors.success;
            button.style.color = 'white';
            button.style.borderColor = DashboardConfig.colors.success;
            
            if (window.notifications) {
                window.notifications.success('Insight aplicado correctamente');
            }
        }, 1500);
    }
    
    refreshInsights() {
        const refreshBtn = document.querySelector('.btn-refresh-insights');
        const icon = refreshBtn.querySelector('i');
        
        // Animar icono de refresh
        icon.style.animation = 'spin 1s linear infinite';
        refreshBtn.disabled = true;
        
        setTimeout(() => {
            icon.style.animation = '';
            refreshBtn.disabled = false;
            
            if (window.notifications) {
                window.notifications.info('Insights actualizados con nuevos datos');
            }
            
            // Simular actualización de insights
            this.updateInsightsContent();
        }, 2000);
    }
    
    updateInsightsContent() {
        // Simular actualización del contenido de insights
        const insightCards = document.querySelectorAll('.insight-card');
        insightCards.forEach((card, index) => {
            card.style.opacity = '0.5';
            setTimeout(() => {
                card.style.opacity = '1';
                card.style.transform = 'scale(1.02)';
                setTimeout(() => {
                    card.style.transform = 'scale(1)';
                }, 200);
            }, index * 200);
        });
    }
}

// ===================================
// GESTIÓN DE DATOS EN TIEMPO REAL
// ===================================

class RealTimeManager {
    constructor() {
        this.updateInterval = null;
        this.isActive = false;
    }
    
    start(interval = 30000) { // 30 segundos por defecto
        if (this.isActive) return;
        
        this.isActive = true;
        this.updateInterval = setInterval(() => {
            this.updateData();
        }, interval);
        
        console.log('Actualizaciones en tiempo real iniciadas');
    }
    
    stop() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        this.isActive = false;
        console.log('Actualizaciones en tiempo real detenidas');
    }
    
    updateData() {
        // Simular actualización de datos en tiempo real
        const mockData = {
            entrenamientos: Math.floor(Math.random() * 10) + 1,
            calorias: Math.floor(Math.random() * 500) + 200,
            volumen: Math.floor(Math.random() * 2000) + 1000
        };
        
        // Actualizar elementos en la página
        this.updateRealTimeElements(mockData);
    }
    
    updateRealTimeElements(data) {
        // Actualizar indicadores en tiempo real
        const indicators = document.querySelectorAll('.real-time-indicator');
        indicators.forEach(indicator => {
            const metric = indicator.getAttribute('data-metric');
            if (data[metric] !== undefined) {
                const valueElement = indicator.querySelector('.value');
                if (valueElement) {
                    Utils.animateNumber(valueElement, data[metric]);
                }
            }
        });
        
        // Actualizar pulse dots
        const pulseDots = document.querySelectorAll('.pulse-dot');
        pulseDots.forEach(dot => {
            dot.style.animation = 'none';
            setTimeout(() => {
                dot.style.animation = 'pulse 2s infinite';
            }, 10);
        });
    }
}

// ===================================
// GESTIÓN DE PERFORMANCE
// ===================================

class PerformanceManager {
    constructor() {
        this.metrics = {};
        this.initPerformanceMonitoring();
    }
    
    initPerformanceMonitoring() {
        // Monitorear tiempo de carga
        window.addEventListener('load', () => {
            this.recordMetric('pageLoad', performance.now());
        });
        
        // Monitorear interacciones
        document.addEventListener('click', (e) => {
            this.recordInteraction(e.target);
        });
    }
    
    recordMetric(name, value) {
        this.metrics[name] = value;
        console.log(`Métrica registrada: ${name} = ${value}ms`);
    }
    
    recordInteraction(element) {
        const elementType = element.tagName.toLowerCase();
        const elementClass = element.className;
        
        console.log(`Interacción: ${elementType}.${elementClass}`);
    }
    
    getMetrics() {
        return this.metrics;
    }
    
    optimizeImages() {
        // Lazy loading para imágenes
        const images = document.querySelectorAll('img[data-src]');
        const imageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                    imageObserver.unobserve(img);
                }
            });
        });
        
        images.forEach(img => imageObserver.observe(img));
    }
}

// ===================================
// INICIALIZACIÓN PRINCIPAL
// ===================================

function initializeDashboard(chartData = {}) {
    console.log('🚀 Inicializando Dashboard Liftin Mejorado...');
    
    // Crear instancias globales
    window.notifications = new NotificationSystem();
    window.chartManager = new ChartManager();
    window.animationManager = new AnimationManager();
    window.filterManager = new FilterManager();
    window.challengeManager = new ChallengeManager();
    window.insightManager = new InsightManager();
    window.realTimeManager = new RealTimeManager();
    window.performanceManager = new PerformanceManager();
    
    // Inicializar componentes
    initializeComponents(chartData);
    
    // Configurar eventos globales
    setupGlobalEvents();
    
    // Optimizaciones
    window.performanceManager.optimizeImages();
    
    // Mostrar notificación de bienvenida
    setTimeout(() => {
        window.notifications.success('¡Dashboard cargado correctamente! 🎉');
    }, 1000);
    
    console.log('✅ Dashboard inicializado correctamente');
}

function initializeComponents(chartData) {
    // Inicializar gráficos
    if (document.getElementById('progressChart')) {
        window.chartManager.createProgressChart('progressChart', chartData);
    }
    
    if (document.getElementById('distributionChart')) {
        window.chartManager.createDistributionChart('distributionChart', chartData);
    }
    
    // Configurar observadores de animación
    document.querySelectorAll('.stat-card-modern, .challenge-card-modern, .insight-card').forEach(element => {
        window.animationManager.observeElement(element);
    });
    
    // Animar contadores iniciales
    setTimeout(() => {
        window.animationManager.animateCounters();
    }, 500);
    
    // Iniciar actualizaciones en tiempo real (opcional)
    // window.realTimeManager.start();
}

function setupGlobalEvents() {
    // Manejo de errores globales
    window.addEventListener('error', (e) => {
        console.error('Error global:', e.error);
        if (window.notifications) {
            window.notifications.error('Ha ocurrido un error inesperado');
        }
    });
    
    // Manejo de cambio de visibilidad de la página
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            window.realTimeManager?.stop();
        } else {
            // Reactivar actualizaciones cuando la página vuelve a ser visible
            setTimeout(() => {
                window.realTimeManager?.start();
            }, 1000);
        }
    });
    
    // Manejo de redimensionamiento de ventana
    window.addEventListener('resize', Utils.debounce(() => {
        // Redimensionar gráficos
        Object.values(window.chartManager.charts).forEach(chart => {
            chart.resize();
        });
    }, 250));
    
    // Atajos de teclado
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + R para refrescar insights
        if ((e.ctrlKey || e.metaKey) && e.key === 'r' && e.shiftKey) {
            e.preventDefault();
            window.insightManager?.refreshInsights();
        }
    });
}

// ===================================
// UTILIDADES ADICIONALES
// ===================================

// Función para exportar datos del dashboard
function exportDashboardData() {
    const data = {
        timestamp: new Date().toISOString(),
        metrics: window.performanceManager?.getMetrics() || {},
        charts: Object.keys(window.chartManager?.charts || {}),
        notifications: window.notifications ? 'active' : 'inactive'
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `dashboard-data-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

// Función para imprimir dashboard
function printDashboard() {
    window.print();
}

// Función para modo pantalla completa
function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
    } else {
        document.exitFullscreen();
    }
}

// Función para cambiar tema (si se implementa modo oscuro)
function toggleTheme() {
    document.body.classList.toggle('dark-theme');
    localStorage.setItem('dashboard-theme', 
        document.body.classList.contains('dark-theme') ? 'dark' : 'light');
}

// Cargar tema guardado
function loadSavedTheme() {
    const savedTheme = localStorage.getItem('dashboard-theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-theme');
    }
}

// ===================================
// ESTILOS CSS ADICIONALES VIA JS
// ===================================

// Agregar estilos de animación adicionales
const additionalStyles = `
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    
    .notification.show {
        animation: slideIn 0.3s ease-out;
    }
    
    .challenge-card-modern.completed {
        border-color: var(--success-color);
        box-shadow: 0 0 20px rgba(74, 222, 128, 0.3);
    }
    
    .dark-theme {
        --bg-primary: #0f172a;
        --bg-secondary: #1e293b;
        --bg-tertiary: #334155;
        --text-primary: #f1f5f9;
        --text-secondary: #cbd5e1;
        --text-muted: #64748b;
    }
`;

// Inyectar estilos adicionales
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
document.head.appendChild(styleSheet);

// ===================================
// INICIALIZACIÓN AUTOMÁTICA
// ===================================

// Cargar tema guardado al inicio
document.addEventListener('DOMContentLoaded', () => {
    loadSavedTheme();
});

// Exportar funciones globales
window.DashboardLiftin = {
    initialize: initializeDashboard,
    export: exportDashboardData,
    print: printDashboard,
    toggleFullscreen: toggleFullscreen,
    toggleTheme: toggleTheme,
    Utils: Utils,
    DashboardConfig: DashboardConfig
};

console.log('📊 Dashboard Liftin Mejorado - JavaScript cargado correctamente');

