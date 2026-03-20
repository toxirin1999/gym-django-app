/**
 * ENTRENAMIENTO ACTIVO - CORE LOGIC
 * Versión corregida para evitar duplicidad de identificadores
 */

// 1. GESTIÓN DE NOTIFICACIONES (Protegida contra doble declaración)
if (typeof window.NotificacionesCodeice === 'undefined') {
    window.NotificacionesCodeice = class NotificacionesCodeice {
        constructor() {
            this.container = document.getElementById('notif-container') || document.body;
            this.notificacionesActivas = [];
        }

        mostrarNotificacion(config) {
            const notif = document.createElement('div');
            notif.className = `notificacion-epica ${config.tipo || ''}`;
            notif.style.cssText = "background:rgba(1,10,19,0.95); border:1px solid #C8AA6E; padding:15px; margin-bottom:10px; border-radius:4px; color:#F0E6D3; position:relative; min-width:250px; box-shadow:0 10px 30px rgba(0,0,0,0.5); transition: all 0.5s ease;";

            notif.innerHTML = `
                <div style="display:flex; align-items:center; gap:10px;">
                    <div style="font-size:24px;">${config.icono}</div>
                    <div>
                        <div style="font-weight:bold; color:#C8AA6E; text-transform:uppercase; font-size:12px;">${config.titulo}</div>
                        <div style="font-size:14px;">${config.mensaje}</div>
                    </div>
                </div>
            `;

            this.container.appendChild(notif);
            setTimeout(() => notif.style.opacity = "1", 100);
            setTimeout(() => {
                notif.style.opacity = "0";
                setTimeout(() => notif.remove(), 500);
            }, config.duracion || 4000);
        }

        mostrarPuntosGanados(puntos) {
            this.mostrarNotificacion({icono: '💰', titulo: '¡Puntos!', mensaje: `+${puntos} puntos`, tipo: 'puntos'});
        }

        mostrarPruebaCompletada(n, p) {
            this.mostrarNotificacion({icono: '⚔️', titulo: 'Prueba Superada', mensaje: n, tipo: 'prueba'});
        }

        mostrarAscension(a, n) {
            this.mostrarNotificacion({
                icono: '🔥',
                titulo: '¡ASCENSIÓN!',
                mensaje: `${a} → ${n}`,
                tipo: 'ascension',
                duracion: 6000
            });
        }

        mostrarRacha(d) {
            this.mostrarNotificacion({icono: '🔥', titulo: 'Racha', mensaje: `${d} días seguidos`, tipo: 'pacha'});
        }
    };
}

if (!window.notificacionesCodeice) {
    window.notificacionesCodeice = new window.NotificacionesCodeice();
}

// 2. CÁLCULO DE PESO POR LADO (Revisado)
window.actualizarPesoPorLado = function (input) {
    const card = input.closest('.cyber-ejercicio-card');
    if (!card) return;

    const nombreEjercicio = card.querySelector('.cyber-ejercicio-nombre')?.textContent || '';
    const peso = parseFloat(input.value.replace(',', '.')) || 0;
    const display = card.querySelector('.weight-per-side-display');
    if (!display) return;

    // Lógica simplificada de discos
    let pesoBarra = nombreEjercicio.toLowerCase().includes('mancuerna') ? 0 : 20;
    const pesoPorLado = (peso - pesoBarra) / 2;

    if (peso > pesoBarra && pesoPorLado > 0) {
        display.innerHTML = `<span style="color:#C8AA6E; font-family:monospace;">+${pesoPorLado.toFixed(1)}kg /lado</span>`;
    } else {
        display.innerHTML = `<span style="color:rgba(200,200,200,0.3); font-size:10px;">Peso base: ${pesoBarra}kg</span>`;
    }
};

// 3. CONTROLADORES DE PESO (+ / -)
document.addEventListener("click", (e) => {
    const btn = e.target.closest(".quick-btn");
    if (!btn) return;

    const container = btn.closest(".peso-ctrl");
    const input = container ? container.querySelector(".weight-input") : null;
    if (!input) return;

    let val = parseFloat(input.value.replace(',', '.')) || 0;
    const step = 2.5; // Salto estándar

    if (btn.classList.contains("quick-plus")) val += step;
    else if (btn.classList.contains("quick-minus")) val = Math.max(0, val - step);

    input.value = (Math.round(val * 10) / 10).toFixed(1);

    // Disparar eventos para que el HTML se entere
    input.dispatchEvent(new Event("input", {bubbles: true}));
    input.dispatchEvent(new Event("change", {bubbles: true}));

    // Actualizar visualmente el peso por lado
    window.actualizarPesoPorLado(input);

    if (navigator.vibrate) navigator.vibrate(15);
});

// Bloqueo de teclado en móvil para inputs numéricos
document.addEventListener('DOMContentLoaded', () => {
    const inputs = document.querySelectorAll('.weight-input, .reps-input, .rpe-input');
    inputs.forEach(inp => {
        inp.setAttribute('readonly', true);
        inp.addEventListener('focus', function () {
            this.blur();
        });
    });
    console.log("🎮 Sistema Iron Protocol (JS) inicializado sin conflictos.");
});