// Sistema de Partículas Blade Runner
class BladeRunnerParticles {
    constructor(container) {
        this.container = container;
        this.particles = [];
        this.smokeElements = [];
        this.maxParticles = 150;
        this.maxSmoke = 8;
        this.isActive = true;
        
        this.init();
        this.createSmokeLayers();
        this.animate();
        this.setupEventListeners();
    }
    
    init() {
        // Crear contenedor de partículas
        this.particleContainer = document.createElement('div');
        this.particleContainer.className = 'blade-runner-particles';
        this.particleContainer.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 1;
            overflow: hidden;
        `;
        
        // Crear contenedor de humo
        this.smokeContainer = document.createElement('div');
        this.smokeContainer.className = 'blade-runner-smoke';
        this.smokeContainer.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 0;
            overflow: hidden;
        `;
        
        this.container.appendChild(this.smokeContainer);
        this.container.appendChild(this.particleContainer);
        
        // Generar partículas iniciales
        for (let i = 0; i < this.maxParticles; i++) {
            this.createParticle();
        }
    }
    
    createParticle() {
        const particle = document.createElement('div');
        particle.className = 'dust-particle';
        
        // Propiedades aleatorias
        const size = Math.random() * 3 + 1;
        const opacity = Math.random() * 0.6 + 0.1;
        const speed = Math.random() * 0.5 + 0.1;
        const drift = Math.random() * 0.3 - 0.15;
        
        // Posición inicial
        const x = Math.random() * window.innerWidth;
        const y = window.innerHeight + 50;
        
        particle.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            background: radial-gradient(circle, rgba(255,255,255,${opacity}) 0%, transparent 70%);
            border-radius: 50%;
            left: ${x}px;
            top: ${y}px;
            pointer-events: none;
            will-change: transform;
        `;
        
        // Propiedades de animación
        particle.dataset.speed = speed;
        particle.dataset.drift = drift;
        particle.dataset.x = x;
        particle.dataset.y = y;
        
        this.particleContainer.appendChild(particle);
        this.particles.push(particle);
        
        return particle;
    }
    
    createSmokeLayers() {
        for (let i = 0; i < this.maxSmoke; i++) {
            this.createSmokeLayer(i);
        }
    }
    
    createSmokeLayer(index) {
        const smoke = document.createElement('div');
        smoke.className = `smoke-layer smoke-layer-${index}`;
        
        const size = Math.random() * 400 + 200;
        const opacity = Math.random() * 0.15 + 0.05;
        const x = Math.random() * (window.innerWidth + 200) - 100;
        const y = Math.random() * (window.innerHeight + 200) - 100;
        const rotation = Math.random() * 360;
        const animationDuration = Math.random() * 60 + 40;
        const animationDelay = Math.random() * 20;
        
        smoke.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            background: radial-gradient(ellipse at center, 
                rgba(100, 100, 120, ${opacity}) 0%,
                rgba(80, 80, 100, ${opacity * 0.7}) 30%,
                rgba(60, 60, 80, ${opacity * 0.4}) 60%,
                transparent 100%);
            border-radius: 50%;
            left: ${x}px;
            top: ${y}px;
            transform: rotate(${rotation}deg);
            filter: blur(${Math.random() * 3 + 1}px);
            animation: smokeFloat ${animationDuration}s linear infinite;
            animation-delay: ${animationDelay}s;
            pointer-events: none;
            will-change: transform;
        `;
        
        this.smokeContainer.appendChild(smoke);
        this.smokeElements.push(smoke);
    }
    
    updateParticles() {
        this.particles.forEach((particle, index) => {
            const speed = parseFloat(particle.dataset.speed);
            const drift = parseFloat(particle.dataset.drift);
            let x = parseFloat(particle.dataset.x);
            let y = parseFloat(particle.dataset.y);
            
            // Movimiento hacia arriba con deriva lateral
            y -= speed;
            x += drift;
            
            // Efecto de turbulencia sutil
            x += Math.sin(Date.now() * 0.001 + index) * 0.1;
            
            // Resetear partícula si sale de la pantalla
            if (y < -50 || x < -50 || x > window.innerWidth + 50) {
                y = window.innerHeight + 50;
                x = Math.random() * window.innerWidth;
            }
            
            // Actualizar posición
            particle.style.left = x + 'px';
            particle.style.top = y + 'px';
            particle.dataset.x = x;
            particle.dataset.y = y;
        });
    }
    
    animate() {
        if (!this.isActive) return;
        
        this.updateParticles();
        requestAnimationFrame(() => this.animate());
    }
    
    setupEventListeners() {
        // Pausar animaciones cuando la pestaña no está visible
        document.addEventListener('visibilitychange', () => {
            this.isActive = !document.hidden;
            if (this.isActive) {
                this.animate();
            }
        });
        
        // Ajustar al redimensionar ventana
        window.addEventListener('resize', () => {
            this.handleResize();
        });
        
        // Efecto de interacción con el mouse
        document.addEventListener('mousemove', (e) => {
            this.handleMouseMove(e);
        });
    }
    
    handleResize() {
        // Reposicionar elementos que están fuera de la nueva ventana
        this.particles.forEach(particle => {
            const x = parseFloat(particle.dataset.x);
            if (x > window.innerWidth) {
                particle.dataset.x = Math.random() * window.innerWidth;
                particle.style.left = particle.dataset.x + 'px';
            }
        });
    }
    
    handleMouseMove(e) {
        // Crear efecto de perturbación sutil alrededor del mouse
        const mouseX = e.clientX;
        const mouseY = e.clientY;
        const influence = 50;
        
        this.particles.forEach(particle => {
            const x = parseFloat(particle.dataset.x);
            const y = parseFloat(particle.dataset.y);
            const distance = Math.sqrt((x - mouseX) ** 2 + (y - mouseY) ** 2);
            
            if (distance < influence) {
                const force = (influence - distance) / influence;
                const angle = Math.atan2(y - mouseY, x - mouseX);
                const pushX = Math.cos(angle) * force * 2;
                const pushY = Math.sin(angle) * force * 2;
                
                particle.dataset.x = x + pushX;
                particle.dataset.y = y + pushY;
            }
        });
    }
    
    // Métodos de control
    pause() {
        this.isActive = false;
    }
    
    resume() {
        this.isActive = true;
        this.animate();
    }
    
    setIntensity(level) {
        // level: 'low', 'medium', 'high'
        const intensities = {
            low: { particles: 50, smoke: 4, opacity: 0.3 },
            medium: { particles: 100, smoke: 6, opacity: 0.6 },
            high: { particles: 200, smoke: 10, opacity: 1 }
        };
        
        const config = intensities[level] || intensities.medium;
        
        // Ajustar número de partículas
        while (this.particles.length > config.particles) {
            const particle = this.particles.pop();
            particle.remove();
        }
        
        while (this.particles.length < config.particles) {
            this.createParticle();
        }
        
        // Ajustar opacidad general
        this.particleContainer.style.opacity = config.opacity;
        this.smokeContainer.style.opacity = config.opacity * 0.8;
    }
    
    destroy() {
        this.isActive = false;
        this.particleContainer.remove();
        this.smokeContainer.remove();
    }
}

// Función de inicialización
function initBladeRunnerEffects() {
    // Verificar si el dispositivo puede manejar las animaciones
    const isLowPowerDevice = /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    // Crear el sistema de partículas
    const particleSystem = new BladeRunnerParticles(document.body);
    
    // Ajustar intensidad según el dispositivo
    if (isLowPowerDevice) {
        particleSystem.setIntensity('low');
    } else {
        particleSystem.setIntensity('medium');
    }
    
    // Exponer controles globalmente
    window.bladeRunnerEffects = particleSystem;
    
    return particleSystem;
}

// Auto-inicialización cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initBladeRunnerEffects);
} else {
    initBladeRunnerEffects();
}

