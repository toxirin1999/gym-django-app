// =====================================================
// PANEL DE ESTIRAMIENTOS - JAVASCRIPT
// Selector de categoría (segmented control) + toggle
// "ver todas las sesiones" por categoría. Sustituye al
// buscador/filtros de texto anteriores.
// =====================================================

document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.mv-tab');
    const panels = document.querySelectorAll('.mv-panel');

    function activarTab(target) {
        tabs.forEach(tab => {
            const activo = tab.dataset.tabTarget === target;
            tab.classList.toggle('is-active', activo);
            tab.setAttribute('aria-selected', activo ? 'true' : 'false');
        });
        panels.forEach(panel => {
            panel.hidden = panel.id !== target;
        });
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', () => activarTab(tab.dataset.tabTarget));
    });

    document.querySelectorAll('.mv-ver-todas').forEach(boton => {
        const seccion = boton.dataset.verTodas;
        const grid = document.querySelector(`.plans-grid[data-plan-section="${seccion}"]`);
        if (!grid) return;
        const textoInicial = boton.textContent;
        boton.addEventListener('click', () => {
            const mostrando = grid.classList.toggle('mostrar-todas');
            boton.textContent = mostrando ? 'Mostrar menos' : textoInicial;
        });
    });
});
