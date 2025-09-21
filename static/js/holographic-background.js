// ========================  SISTEMA DE PARTÍCULAS HOLOGRÁFICAS  ========================

class HolographicBackground {
  constructor() {
    this.container = null;
    this.particles = [];
    this.particleCount = 50;
    this.isInitialized = false;
    
    this.init();
  }

  init() {
    if (this.isInitialized) return;
    
    this.createContainer();
    this.createParticles();
    this.startAnimations();
    
    this.isInitialized = true;
  }

  createContainer() {
    // Crear el contenedor principal
    this.container = document.createElement('div');
    this.container.className = 'holographic-background';
    
    // Crear las capas de niebla
    const fog1 = document.createElement('div');
    fog1.className = 'holographic-fog';
    
    const fog2 = document.createElement('div');
    fog2.className = 'holographic-fog-2';
    
    // Crear las capas de gradientes
    const gradients1 = document.createElement('div');
    gradients1.className = 'shifting-gradients';
    
    const gradients2 = document.createElement('div');
    gradients2.className = 'shifting-gradients-2';
    
    // Crear el contenedor de partículas
    const particlesContainer = document.createElement('div');
    particlesContainer.className = 'particles-container';
    
    // Crear línea de escaneo
    const scanLine = document.createElement('div');
    scanLine.className = 'holographic-scan';
    
    // Crear pulsos de energía
    for (let i = 0; i < 3; i++) {
      const pulse = document.createElement('div');
      pulse.className = 'energy-pulse';
      this.container.appendChild(pulse);
    }
    
    // Ensamblar el contenedor
    this.container.appendChild(fog1);
    this.container.appendChild(fog2);
    this.container.appendChild(gradients1);
    this.container.appendChild(gradients2);
    this.container.appendChild(particlesContainer);
    this.container.appendChild(scanLine);
    
    // Añadir al body
    document.body.appendChild(this.container);
    
    this.particlesContainer = particlesContainer;
  }

  createParticles() {
    const colors = [
      { class: 'small', color: 'rgba(160, 108, 254, 0.5)' },
      { class: '', color: 'rgba(49, 207, 244, 0.6)' },
      { class: 'medium', color: 'rgba(0, 245, 160, 0.4)' },
      { class: 'large', color: 'rgba(255, 204, 0, 0.3)' }
    ];

    for (let i = 0; i < this.particleCount; i++) {
      const particle = document.createElement('div');
      const colorData = colors[Math.floor(Math.random() * colors.length)];
      
      particle.className = `particle ${colorData.class}`;
      
      // Posición inicial aleatoria
      const startX = Math.random() * window.innerWidth;
      particle.style.left = startX + 'px';
      
      // Velocidad y duración aleatoria
      const duration = 15 + Math.random() * 20; // 15-35 segundos
      const delay = Math.random() * 10; // 0-10 segundos de retraso
      
      // Seleccionar animación aleatoria
      const animations = ['floatUp1', 'floatUp2', 'floatUp3'];
      const animation = animations[Math.floor(Math.random() * animations.length)];
      
      particle.style.animation = `${animation} ${duration}s linear ${delay}s infinite`;
      
      this.particlesContainer.appendChild(particle);
      this.particles.push(particle);
    }
  }

  startAnimations() {
    // Crear efectos adicionales de parpadeo
    this.createGlitchEffect();
    
    // Iniciar ciclo de regeneración de partículas
    this.startParticleRegeneration();
  }

  createGlitchEffect() {
    setInterval(() => {
      if (Math.random() < 0.1) { // 10% de probabilidad
        const randomParticles = this.particles
          .sort(() => 0.5 - Math.random())
          .slice(0, 5);
        
        randomParticles.forEach(particle => {
          particle.style.opacity = '0';
          setTimeout(() => {
            particle.style.opacity = '1';
          }, 100);
        });
      }
    }, 3000);
  }

  startParticleRegeneration() {
    // Regenerar algunas partículas periódicamente para mantener el efecto dinámico
    setInterval(() => {
      const particlesToRegenerate = Math.floor(this.particleCount * 0.1); // 10% de las partículas
      
      for (let i = 0; i < particlesToRegenerate; i++) {
        const randomIndex = Math.floor(Math.random() * this.particles.length);
        const particle = this.particles[randomIndex];
        
        // Reiniciar la posición
        const newX = Math.random() * window.innerWidth;
        particle.style.left = newX + 'px';
        
        // Reiniciar la animación
        particle.style.animation = 'none';
        particle.offsetHeight; // Forzar reflow
        
        const duration = 15 + Math.random() * 20;
        const animations = ['floatUp1', 'floatUp2', 'floatUp3'];
        const animation = animations[Math.floor(Math.random() * animations.length)];
        
        particle.style.animation = `${animation} ${duration}s linear infinite`;
      }
    }, 30000); // Cada 30 segundos
  }

  // Método para ajustar la intensidad de las animaciones
  setIntensity(level) {
    const intensities = {
      low: { particleCount: 30, animationSpeed: 0.5 },
      medium: { particleCount: 50, animationSpeed: 1 },
      high: { particleCount: 80, animationSpeed: 1.5 }
    };
    
    const intensity = intensities[level] || intensities.medium;
    
    // Ajustar velocidad de animaciones
    const style = document.createElement('style');
    style.textContent = `
      .holographic-fog { animation-duration: ${20 / intensity.animationSpeed}s !important; }
      .holographic-fog-2 { animation-duration: ${25 / intensity.animationSpeed}s !important; }
      .shifting-gradients { animation-duration: ${30 / intensity.animationSpeed}s !important; }
      .shifting-gradients-2 { animation-duration: ${35 / intensity.animationSpeed}s !important; }
    `;
    document.head.appendChild(style);
  }

  // Método para pausar/reanudar animaciones
  toggleAnimations(pause = false) {
    const animationState = pause ? 'paused' : 'running';
    this.container.style.animationPlayState = animationState;
    
    this.particles.forEach(particle => {
      particle.style.animationPlayState = animationState;
    });
  }

  // Método para destruir el sistema (útil para limpieza)
  destroy() {
    if (this.container && this.container.parentNode) {
      this.container.parentNode.removeChild(this.container);
    }
    this.particles = [];
    this.isInitialized = false;
  }
}

// ========================  INICIALIZACIÓN AUTOMÁTICA  ========================

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
  // Verificar si el usuario prefiere movimiento reducido
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  
  if (!prefersReducedMotion) {
    // Crear instancia global del sistema de fondo holográfico
    window.holographicBg = new HolographicBackground();
    
    // Ajustar intensidad basada en el rendimiento del dispositivo
    const isLowEndDevice = navigator.hardwareConcurrency <= 2 || 
                          /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (isLowEndDevice) {
      window.holographicBg.setIntensity('low');
    } else {
      window.holographicBg.setIntensity('medium');
    }
  }
});

// Pausar animaciones cuando la pestaña no está visible (optimización de rendimiento)
document.addEventListener('visibilitychange', function() {
  if (window.holographicBg) {
    window.holographicBg.toggleAnimations(document.hidden);
  }
});

// Ajustar partículas cuando cambie el tamaño de la ventana
window.addEventListener('resize', function() {
  if (window.holographicBg) {
    // Recrear partículas con nuevas posiciones
    setTimeout(() => {
      window.holographicBg.destroy();
      window.holographicBg = new HolographicBackground();
    }, 500);
  }
});

// ========================  UTILIDADES ADICIONALES  ========================

// Función para crear efectos de pulso en elementos específicos
function addHolographicPulse(element, color = 'rgba(49, 207, 244, 0.3)') {
  element.style.position = 'relative';
  element.style.overflow = 'hidden';
  
  const pulse = document.createElement('div');
  pulse.style.position = 'absolute';
  pulse.style.top = '0';
  pulse.style.left = '0';
  pulse.style.width = '100%';
  pulse.style.height = '100%';
  pulse.style.background = `radial-gradient(circle, ${color} 0%, transparent 70%)`;
  pulse.style.opacity = '0';
  pulse.style.animation = 'energyPulse 3s ease-in-out infinite';
  pulse.style.pointerEvents = 'none';
  
  element.appendChild(pulse);
}

// Función para añadir efecto de escaneo a elementos
function addScanEffect(element) {
  element.style.position = 'relative';
  element.style.overflow = 'hidden';
  
  const scan = document.createElement('div');
  scan.style.position = 'absolute';
  scan.style.top = '0';
  scan.style.left = '0';
  scan.style.width = '100%';
  scan.style.height = '2px';
  scan.style.background = 'linear-gradient(90deg, transparent 0%, rgba(49, 207, 244, 0.8) 50%, transparent 100%)';
  scan.style.animation = 'scanLine 4s linear infinite';
  scan.style.pointerEvents = 'none';
  
  element.appendChild(scan);
}

