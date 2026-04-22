/**
 * dashboard.js — Logic for collapsible dashboard sections.
 */

window.Dashboard = (function() {
    /**
     * Toggles a dashboard section's collapsed state.
     * @param {string} id - The section ID (e.g., 'net-worth').
     */
    function toggleSection(id) {
        const section = document.getElementById(`section-${id}`);
        const content = document.getElementById(`content-${id}`);
        const summary = document.getElementById(`summary-${id}`);
        const chevron = document.getElementById(`chevron-${id}`);
        const viewAll = section.querySelector('.view-all-link');
        
        const isCollapsed = section.getAttribute('data-state') === 'collapsed';
        
        if (isCollapsed) {
            // Expand
            section.setAttribute('data-state', 'expanded');
            if (content) content.classList.remove('hidden');
            if (summary) summary.classList.add('hidden');
            if (chevron) chevron.classList.remove('-rotate-90');
            if (viewAll) viewAll.classList.remove('hidden');
            localStorage.setItem(`dashboard-section-${id}`, 'expanded');
            section.querySelector('[role="button"]').setAttribute('aria-expanded', 'true');
        } else {
            // Collapse
            section.setAttribute('data-state', 'collapsed');
            if (content) content.classList.add('hidden');
            if (summary) summary.classList.remove('hidden');
            if (chevron) chevron.classList.add('-rotate-90');
            if (viewAll) viewAll.classList.add('hidden');
            localStorage.setItem(`dashboard-section-${id}`, 'collapsed');
            section.querySelector('[role="button"]').setAttribute('aria-expanded', 'false');
        }
    }

    /**
     * Initializes sections based on stored preference in localStorage.
     */
    function init() {
        document.querySelectorAll('[data-section]').forEach(section => {
            const id = section.dataset.section;
            const state = localStorage.getItem(`dashboard-section-${id}`);
            if (state === 'collapsed') {
                const content = document.getElementById(`content-${id}`);
                const summary = document.getElementById(`summary-${id}`);
                const chevron = document.getElementById(`chevron-${id}`);
                const viewAll = section.querySelector('.view-all-link');
                
                section.setAttribute('data-state', 'collapsed');
                if (content) content.classList.add('hidden');
                if (summary) summary.classList.remove('hidden');
                if (chevron) chevron.classList.add('-rotate-90');
                if (viewAll) viewAll.classList.add('hidden');
                const btn = section.querySelector('[role="button"]');
                if (btn) btn.setAttribute('aria-expanded', 'false');
            } else {
                section.setAttribute('data-state', 'expanded');
            }
        });
    }

    return {
        toggleSection,
        init
    };
})();

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', function() {
    Dashboard.init();
});

// Re-init after HTMX swaps
document.addEventListener('htmx:afterSettle', function() {
    Dashboard.init();
});
