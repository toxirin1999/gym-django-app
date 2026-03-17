// =====================================================
// PANEL DE ESTIRAMIENTOS - JAVASCRIPT
// =====================================================

class StretchPanel {
    constructor() {
        this.plans = [];
        this.filteredPlans = [];
        this.currentFilter = 'all';

        this.elements = {
            searchInput: document.getElementById('searchInput'),
            filterButtons: document.querySelectorAll('.filter-btn'),
            plansGrid: document.querySelector('.plans-grid'),
            planCards: document.querySelectorAll('.plan-card')
        };

        this.init();
    }

    init() {
        // Cachear planes
        this.cachePlans();

        // Event listeners
        if (this.elements.searchInput) {
            this.elements.searchInput.addEventListener('input', (e) => this.handleSearch(e.target.value));
        }

        this.elements.filterButtons.forEach(btn => {
            btn.addEventListener('click', (e) => this.handleFilter(e.currentTarget.dataset.filter));
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === '/' && e.target.tagName !== 'INPUT') {
                e.preventDefault();
                this.elements.searchInput?.focus();
            }
        });
    }

    cachePlans() {
        this.elements.planCards.forEach(card => {
            this.plans.push({
                element: card,
                name: card.querySelector('.plan-title')?.textContent.toLowerCase() || '',
                description: card.querySelector('.plan-description')?.textContent.toLowerCase() || '',
                type: card.classList.contains('superior') ? 'superior' :
                    card.classList.contains('inferior') ? 'inferior' : 'completo'
            });
        });
        this.filteredPlans = [...this.plans];
    }

    handleSearch(query) {
        const searchTerm = query.toLowerCase().trim();

        this.filteredPlans = this.plans.filter(plan => {
            const matchesSearch = !searchTerm ||
                plan.name.includes(searchTerm) ||
                plan.description.includes(searchTerm);

            const matchesFilter = this.currentFilter === 'all' ||
                plan.type === this.currentFilter;

            return matchesSearch && matchesFilter;
        });

        this.renderPlans();
    }

    handleFilter(filter) {
        this.currentFilter = filter;

        // Update button states
        this.elements.filterButtons.forEach(btn => {
            if (btn.dataset.filter === filter) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Re-apply search with new filter
        const searchTerm = this.elements.searchInput?.value || '';
        this.handleSearch(searchTerm);
    }

    renderPlans() {
        // Hide all plans first
        this.plans.forEach(plan => {
            plan.element.classList.add('hidden');
        });

        // Show filtered plans
        this.filteredPlans.forEach((plan, index) => {
            plan.element.classList.remove('hidden');
            // Re-trigger animation
            plan.element.style.animationDelay = `${index * 0.1}s`;
        });

        // Show no results message if needed
        if (this.filteredPlans.length === 0) {
            this.showNoResults();
        } else {
            this.hideNoResults();
        }
    }

    showNoResults() {
        let noResults = document.getElementById('noResults');
        if (!noResults) {
            noResults = document.createElement('div');
            noResults.id = 'noResults';
            noResults.className = 'no-plans';
            noResults.innerHTML = `
                <i class="fas fa-search"></i>
                <p>No se encontraron planes que coincidan con tu búsqueda.</p>
            `;
            this.elements.plansGrid.appendChild(noResults);
        }
        noResults.classList.remove('hidden');
    }

    hideNoResults() {
        const noResults = document.getElementById('noResults');
        if (noResults) {
            noResults.classList.add('hidden');
        }
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    window.stretchPanel = new StretchPanel();
});
