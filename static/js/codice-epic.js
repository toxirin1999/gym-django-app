
<script>
/* ============================================================================
   JAVASCRIPT ÉPICO PARA ANIMACIONES AVANZADAS
   ============================================================================ */

class AnimacionesEpicas {
    constructor() {
        this.init();
    }
    
    init() {
        this.crearParticulas();
        this.animarElementosEnVista();
        this.efectosHover();
        this.animacionesDeConteo();
    }
    
    // Crear partículas flotantes épicas
    crearParticulas() {
        const containers = document.querySelectorAll('.codice-widget-epic');
        
        containers.forEach(container => {
            if (!container.querySelector('.particles-container')) {
                const particlesContainer = document.createElement('div');
                particlesContainer.className = 'particles-container';
                
                for (let i = 0; i < 10; i++) {
                    const particle = document.createElement('div');
                    particle.className = 'particle';
                    particle.style.left = Math.random() * 100 + '%';
                    particle.style.animationDelay = Math.random() * 3 + 's';
                    particle.style.animationDuration = (Math.random() * 2 + 2) + 's';
                    particlesContainer.appendChild(particle);
                }
                
                container.appendChild(particlesContainer);
            }
        });
    }
    
    // Animar elementos cuando entran en vista
    animarElementosEnVista() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('fade-in-epic');
                }
            });
        }, { threshold: 0.1 });
        
        document.querySelectorAll('.codice-widget-epic, .stat-epic').forEach(el => {
            observer.observe(el);
        });
    }
    
    // Efectos hover épicos
    efectosHover() {
        document.querySelectorAll('.arquetipo-avatar-epic').forEach(avatar => {
            avatar.addEventListener('mouseenter', () => {
                this.crearEfectoHover(avatar);
            });
        });
    }
    
    crearEfectoHover(element) {
        const ripple = document.createElement('div');
        ripple.style.position = 'absolute';
        ripple.style.borderRadius = '50%';
        ripple.style.background = 'rgba(255, 215, 0, 0.6)';
        ripple.style.transform = 'scale(0)';
        ripple.style.animation = 'ripple 0.6s linear';
        ripple.style.left = '50%';
        ripple.style.top = '50%';
        ripple.style.width = '100px';
        ripple.style.height = '100px';
        ripple.style.marginLeft = '-50px';
        ripple.style.marginTop = '-50px';
        
        element.style.position = 'relative';
        element.appendChild(ripple);
        
        setTimeout(() => {
            ripple.remove();
        }, 600);
    }
    
    // Animaciones de conteo épicas
    animacionesDeConteo() {
        document.querySelectorAll('.stat-value-epic').forEach(element => {
            this.animarConteo(element);
        });
    }
    
    animarConteo(element) {
        const finalValue = parseInt(element.textContent.replace(/\D/g, ''));
        if (isNaN(finalValue)) return;
        
        const duration = 2000;
        const startTime = performance.now();
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            const currentValue = Math.floor(finalValue * this.easeOutQuart(progress));
            element.textContent = element.textContent.replace(/\d+/, currentValue);
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }
    
    easeOutQuart(t) {
        return 1 - (--t) * t * t * t;
    }
    
    // Efecto de ascensión épico
    mostrarEfectoAscension(elemento) {
        elemento.classList.add('ascension-effect');
        
        // Crear partículas de ascensión
        for (let i = 0; i < 20; i++) {
            const particle = document.createElement('div');
            particle.innerHTML = '✨';
            particle.style.position = 'absolute';
            particle.style.left = Math.random() * 100 + '%';
            particle.style.top = Math.random() * 100 + '%';
            particle.style.fontSize = '1rem';
            particle.style.pointerEvents = 'none';
            particle.style.animation = 'particleFloat 2s ease-out forwards';
            particle.style.animationDelay = Math.random() * 0.5 + 's';
            
            elemento.appendChild(particle);
            
            setTimeout(() => particle.remove(), 2500);
        }
        
        setTimeout(() => {
            elemento.classList.remove('ascension-effect');
        }, 1000);
    }
    
    // Efecto de nueva prueba desbloqueada
    mostrarEfectoNuevaPrueba(elemento) {
        elemento.classList.add('nueva-prueba-effect');
        
        setTimeout(() => {
            elemento.classList.remove('nueva-prueba-effect');
        }, 3000);
    }
    
    // Efecto de récord superado
    mostrarEfectoRecord(elemento) {
        elemento.classList.add('record-superado-effect');
        
        setTimeout(() => {
            elemento.classList.remove('record-superado-effect');
        }, 800);
    }
}

// Inicializar animaciones épicas cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    window.animacionesEpicas = new AnimacionesEpicas();
    console.log('🎮 Animaciones épicas del Códice inicializadas');
});

// Funciones globales para usar desde otros scripts
window.mostrarEfectoAscension = (elemento) => {
    window.animacionesEpicas.mostrarEfectoAscension(elemento);
};

window.mostrarEfectoNuevaPrueba = (elemento) => {
    window.animacionesEpicas.mostrarEfectoNuevaPrueba(elemento);
};

window.mostrarEfectoRecord = (elemento) => {
    window.animacionesEpicas.mostrarEfectoRecord(elemento);
};

// CSS adicional para el efecto ripple
const style = document.createElement('style');
style.textContent = `
@keyframes ripple {
    to {
        transform: scale(4);
        opacity: 0;
    }
}
`;
document.head.appendChild(style);
</script>