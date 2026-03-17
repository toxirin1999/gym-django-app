// ========================================
// DETALLE CLIENTE - MODERN INTERACTIONS
// ========================================

document.addEventListener('DOMContentLoaded', function () {
    initAccordions();
    initChart();
    initAnimations();
    initTooltips();
});

// ========================================
// ACCORDION FUNCTIONALITY
// ========================================
function initAccordions() {
    const accordionHeaders = document.querySelectorAll('.accordion-header');

    accordionHeaders.forEach(header => {
        header.addEventListener('click', function () {
            const content = this.nextElementSibling;
            const isActive = this.classList.contains('active');

            // Close all accordions
            document.querySelectorAll('.accordion-header').forEach(h => {
                h.classList.remove('active');
                h.setAttribute('aria-expanded', 'false');
            });

            document.querySelectorAll('.accordion-content').forEach(c => {
                c.classList.remove('active');
            });

            // Open clicked accordion if it wasn't active
            if (!isActive) {
                this.classList.add('active');
                this.setAttribute('aria-expanded', 'true');
                content.classList.add('active');
            }
        });

        // Keyboard accessibility
        header.addEventListener('keypress', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.click();
            }
        });
    });
}

// ========================================
// CHART INITIALIZATION
// ========================================
function initChart() {
    const canvas = document.getElementById('progresoGrafico');
    if (!canvas) return;

    const data = window.perfilClienteData;
    if (!data || !data.labels || data.labels.length === 0) return;

    const ctx = canvas.getContext('2d');

    // Gradient for weight line
    const gradientPeso = ctx.createLinearGradient(0, 0, 0, 400);
    gradientPeso.addColorStop(0, 'rgba(200, 170, 110, 0.6)');
    gradientPeso.addColorStop(1, 'rgba(200, 170, 110, 0.0)');

    // Gradient for body fat line
    const gradientGrasa = ctx.createLinearGradient(0, 0, 0, 400);
    gradientGrasa.addColorStop(0, 'rgba(200, 55, 55, 0.6)');
    gradientGrasa.addColorStop(1, 'rgba(200, 55, 55, 0.0)');

    new Chart(ctx, {
        type: 'line',
    data: {
        datasets: [{
                    label: 'Peso (kg)',
                    data: data.pesos,
                    borderColor: '#C8AA6E',
                    backgroundColor: gradientPeso,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    pointBackgroundColor: '#0a0a0c',
                    pointBorderColor: '#c8aa6e',
                    pointBorderWidth: 2,
                    pointHoverBackgroundColor: '#c8aa6e',
                    pointHoverBorderColor: '#fff',
                },
                {
                    label: 'Grasa Corporal (%)',
                    data: data.grasas,
                    borderColor: '#c83737',
                    backgroundColor: gradientGrasa,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    pointBackgroundColor: '#0a0a0c',
                    pointBorderColor: '#c83737',
                    pointBorderWidth: 2,
                    pointHoverBackgroundColor: '#c83737',
                    pointHoverBorderColor: '#fff',
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
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#a09b8c',
                        font: {
                            family: "'Bebas Neue', 'JetBrains Mono', sans-serif",
                            size: 14,
                            weight: 'normal',
                            letterSpacing: '1px'
                        },
                        padding: 20,
                        usePointStyle: true,
                        pointStyle: 'rectRot'
                    }
                },
                tooltip: {
                    enabled: true,
                    backgroundColor: 'rgba(200,170,110,0.08)',
                    titleColor: '#f0e6d2',
                    titleFont: {
                        family: "'Bebas Neue', 'JetBrains Mono', sans-serif",
                        size: 16,
                        letterSpacing: '1px'
                    },
                    bodyColor: '#a09b8c',
                    bodyFont: {
                        family: "'JetBrains Mono', monospace",
                        size: 11
                    },
                    borderColor: 'rgba(200, 170, 110, 0.3)',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        title: function (context) {
                            return context[0].label;
                        },
                        label: function (context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            label += context.parsed.y.toFixed(1);
                            if (context.datasetIndex === 0) {
                                label += ' kg';
                            } else {
                                label += '%';
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    /* grid from defaults */,
                    /* ticks from defaults */
                    }
                },
                y: {
                    /* grid from defaults */,
                    /* ticks from defaults */
                    }
                }
            },
            animation: {
                duration: 1500,
                easing: 'easeInOutQuart'
            }
        }
    });
}

// ========================================
// SCROLL ANIMATIONS
// ========================================
function initAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-fade-in-up');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe stat cards
    document.querySelectorAll('.stat-card').forEach((card, index) => {
        card.style.opacity = '0';
        card.classList.add(`stagger-${(index % 4) + 1}`);
        observer.observe(card);
    });

    // Observe info cards
    document.querySelectorAll('.info-card').forEach((card, index) => {
        card.style.opacity = '0';
        card.classList.add(`stagger-${(index % 2) + 1}`);
        observer.observe(card);
    });
}

// ========================================
// TOOLTIPS (Optional enhancement)
// ========================================
function initTooltips() {
    const tooltipTriggers = document.querySelectorAll('[data-tooltip]');

    tooltipTriggers.forEach(trigger => {
        trigger.addEventListener('mouseenter', function (e) {
            const tooltipText = this.getAttribute('data-tooltip');
            const tooltip = document.createElement('div');
            tooltip.className = 'custom-tooltip';
            tooltip.textContent = tooltipText;
            tooltip.style.cssText = `
                position: absolute;
                background: rgba(0, 0, 0, 0.9);
                color: #00d9ff;
                padding: 0.5rem 1rem;
                border-radius: 8px;
                font-size: 0.875rem;
                pointer-events: none;
                z-index: 1000;
                white-space: nowrap;
                border: 1px solid rgba(0, 217, 255, 0.3);
            `;

            document.body.appendChild(tooltip);

            const rect = this.getBoundingClientRect();
            tooltip.style.top = (rect.top - tooltip.offsetHeight - 10) + 'px';
            tooltip.style.left = (rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2)) + 'px';

            this._tooltip = tooltip;
        });

        trigger.addEventListener('mouseleave', function () {
            if (this._tooltip) {
                this._tooltip.remove();
                delete this._tooltip;
            }
        });
    });
}

// ========================================
// UTILITY FUNCTIONS
// ========================================

// Smooth scroll to element
function scrollToElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
}

// Number counter animation
function animateValue(element, start, end, duration) {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const value = Math.floor(progress * (end - start) + start);
        element.textContent = value;
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

// Expose functions globally if needed
window.detailPageUtils = {
    scrollToElement,
    animateValue
};

console.log('✨ Detalle Cliente - Modern UI Loaded');
