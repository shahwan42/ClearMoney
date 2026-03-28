// category-combobox.js — Searchable category dropdown replacing native <select>.
// Auto-initializes on [data-category-combobox] elements.
// Follows the same IIFE + prototype pattern as bottom-sheet.js.
//
// Usage:
//   <div data-category-combobox
//        data-categories='[{"id":"uuid","name":"Food","icon":"🍕"},...]'
//        data-name="category_id"
//        data-selected-id="optional-uuid"
//        data-placeholder="Search categories..."
//        data-allow-empty="true">
//   </div>
//
// Programmatic selection (used by note-suggestion feature):
//   el._combobox.selectById('uuid')

var CategoryCombobox = (function() {
    // Counter used to generate unique listbox IDs when multiple comboboxes
    // exist on the same page (required by ARIA aria-controls/aria-activedescendant).
    var instanceCount = 0;

    // getCsrfToken reads the CSRF token from the hx-headers attribute on <body>.
    // The app always sets: hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'.
    function getCsrfToken() {
        try {
            var raw = document.body.getAttribute('hx-headers');
            if (raw) return JSON.parse(raw)['X-CSRFToken'] || '';
        } catch (e) { /* ignore parse errors */ }
        return '';
    }

    // CategoryCombobox constructor — replaces a data-category-combobox container
    // with a fully accessible searchable dropdown.
    function CategoryCombobox(container) {
        if (container._combobox) return; // Already initialized — skip
        container._combobox = this;

        instanceCount += 1;
        var uid = instanceCount;

        // Parse configuration from data attributes
        this.container   = container;
        this.categories  = JSON.parse(container.getAttribute('data-categories') || '[]');
        this.name        = container.getAttribute('data-name') || 'category_id';
        this.selectedId  = container.getAttribute('data-selected-id') || '';
        this.placeholder = container.getAttribute('data-placeholder') || 'Search categories...';
        this.allowEmpty  = container.getAttribute('data-allow-empty') === 'true';

        // Runtime state
        this.activeIndex    = -1;  // Keyboard-focused option index within visible options
        this.isOpen         = false;
        this.showAddForm    = false;
        this.listboxId      = 'category-listbox-' + uid;
        this.optionIdPrefix = 'category-option-' + uid + '-';

        this._buildDOM();
        this._attachEvents();

        // Pre-select the category specified by data-selected-id
        if (this.selectedId) {
            this.selectById(this.selectedId);
        }
    }

    // _buildDOM creates and inserts all DOM nodes into the container.
    CategoryCombobox.prototype._buildDOM = function() {
        // Ensure the container is positioned so the absolute dropdown is anchored to it.
        this.container.style.position = 'relative';

        // Hidden input carries the actual form value (category UUID)
        this.hiddenInput = document.createElement('input');
        this.hiddenInput.type  = 'hidden';
        this.hiddenInput.name  = this.name;
        this.hiddenInput.value = this.selectedId || '';

        // Visible text input — user types here to search
        this.textInput = document.createElement('input');
        this.textInput.type         = 'text';
        this.textInput.placeholder  = this.placeholder;
        this.textInput.autocomplete = 'off';
        this.textInput.spellcheck   = false;
        // ARIA combobox role wires the input to the listbox
        this.textInput.setAttribute('role', 'combobox');
        this.textInput.setAttribute('aria-expanded', 'false');
        this.textInput.setAttribute('aria-autocomplete', 'list');
        this.textInput.setAttribute('aria-controls', this.listboxId);
        this.textInput.setAttribute('aria-haspopup', 'listbox');
        this.textInput.className = [
            'w-full border border-gray-200 dark:border-slate-600',
            'dark:bg-slate-800 dark:text-white rounded-lg px-3 py-2.5 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-teal-500'
        ].join(' ');

        // Listbox dropdown container
        this.listbox = document.createElement('div');
        this.listbox.id        = this.listboxId;
        this.listbox.setAttribute('role', 'listbox');
        this.listbox.className = [
            'absolute z-50 mt-1 w-full bg-white dark:bg-slate-800',
            'border border-gray-200 dark:border-slate-600 rounded-lg shadow-lg',
            'max-h-60 overflow-y-auto'
        ].join(' ');
        this.listbox.style.display = 'none';

        this.container.appendChild(this.hiddenInput);
        this.container.appendChild(this.textInput);
        this.container.appendChild(this.listbox);
    };

    // _attachEvents wires up all interaction handlers.
    CategoryCombobox.prototype._attachEvents = function() {
        var self = this;

        // Show dropdown on focus
        this.textInput.addEventListener('focus', function() {
            self._openDropdown();
        });

        // Show dropdown on click (in case focus fired but dropdown was closed)
        this.textInput.addEventListener('click', function() {
            if (!self.isOpen) self._openDropdown();
        });

        // Filter options as user types
        this.textInput.addEventListener('input', function() {
            self.showAddForm = false;
            self._renderOptions();
            if (!self.isOpen) self._openDropdown();
        });

        // Keyboard navigation: ArrowDown, ArrowUp, Enter, Escape
        this.textInput.addEventListener('keydown', function(e) {
            if (!self.isOpen) {
                if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                    e.preventDefault();
                    self._openDropdown();
                }
                return;
            }

            var options = self._getOptionElements();

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                self.activeIndex = Math.min(self.activeIndex + 1, options.length - 1);
                self._updateActiveDescendant(options);

            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                self.activeIndex = Math.max(self.activeIndex - 1, 0);
                self._updateActiveDescendant(options);

            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (self.activeIndex >= 0 && options[self.activeIndex]) {
                    options[self.activeIndex].click();
                }

            } else if (e.key === 'Escape') {
                e.preventDefault();
                self._closeDropdown();
            }
        });

        // Close when clicking outside the container
        document.addEventListener('mousedown', function(e) {
            if (!self.container.contains(e.target)) {
                self._closeDropdown();
            }
        });
    };

    // _openDropdown renders options and shows the listbox.
    CategoryCombobox.prototype._openDropdown = function() {
        this.isOpen = true;
        this.activeIndex = -1;
        this._renderOptions();
        this.listbox.style.display = 'block';
        this.textInput.setAttribute('aria-expanded', 'true');
    };

    // _closeDropdown hides the listbox and resets state.
    CategoryCombobox.prototype._closeDropdown = function() {
        this.isOpen = false;
        this.showAddForm = false;
        this.listbox.style.display = 'none';
        this.textInput.setAttribute('aria-expanded', 'false');
        this.textInput.removeAttribute('aria-activedescendant');
    };

    // _renderOptions rebuilds the listbox contents based on the current search query.
    CategoryCombobox.prototype._renderOptions = function() {
        var self    = this;
        var query   = this.textInput.value.trim().toLowerCase();
        var filtered = this.categories.filter(function(cat) {
            return cat.name.toLowerCase().indexOf(query) !== -1;
        });

        this.listbox.innerHTML = '';

        // "None" option — shown when data-allow-empty="true"
        if (this.allowEmpty) {
            var noneEl = this._makeOptionEl(
                this.optionIdPrefix + 'none',
                '— None',
                '',    // no icon
                this.hiddenInput.value === ''
            );
            noneEl.addEventListener('mousedown', function(e) {
                e.preventDefault(); // Prevent blur before click registers
                self._selectCategory('', '');
            });
            this.listbox.appendChild(noneEl);
        }

        // Filtered category options
        filtered.forEach(function(cat, idx) {
            var isSelected = cat.id === self.hiddenInput.value;
            var optEl = self._makeOptionEl(
                self.optionIdPrefix + idx,
                cat.name,
                cat.icon || '',
                isSelected
            );
            optEl.dataset.categoryId = cat.id;
            optEl.addEventListener('mousedown', function(e) {
                e.preventDefault();
                self._selectCategory(cat.id, (cat.icon ? cat.icon + ' ' : '') + cat.name);
            });
            self.listbox.appendChild(optEl);
        });

        // "+ Add new category" button — always at the bottom
        if (!this.showAddForm) {
            var addBtn = document.createElement('div');
            addBtn.setAttribute('role', 'option');
            addBtn.setAttribute('aria-selected', 'false');
            addBtn.id = this.optionIdPrefix + 'add-new';
            addBtn.className = [
                'px-3 py-2 text-sm text-teal-600 dark:text-teal-400 cursor-pointer',
                'hover:bg-gray-50 dark:hover:bg-slate-700',
                'border-t border-gray-100 dark:border-slate-700 flex items-center gap-1'
            ].join(' ');
            addBtn.innerHTML = '<span aria-hidden="true">+</span> Add new category';
            addBtn.addEventListener('mousedown', function(e) {
                e.preventDefault();
                self.showAddForm = true;
                self._renderOptions();
            });
            this.listbox.appendChild(addBtn);
        } else {
            // Inline "add new category" form inside the dropdown
            this.listbox.appendChild(this._buildAddForm());
        }
    };

    // _makeOptionEl creates a single listbox option element.
    // isSelected applies the highlighted/selected styling.
    CategoryCombobox.prototype._makeOptionEl = function(id, name, icon, isSelected) {
        var el = document.createElement('div');
        el.setAttribute('role', 'option');
        el.setAttribute('aria-selected', isSelected ? 'true' : 'false');
        el.id = id;

        var baseClass = 'px-3 py-2 text-sm cursor-pointer hover:bg-teal-50 dark:hover:bg-slate-700';
        el.className = isSelected
            ? baseClass + ' bg-teal-50 dark:bg-slate-700 font-medium'
            : baseClass;

        el.textContent = icon ? icon + ' ' + name : name;
        return el;
    };

    // _buildAddForm returns the inline form DOM node for creating a new category.
    CategoryCombobox.prototype._buildAddForm = function() {
        var self    = this;
        var wrapper = document.createElement('div');
        wrapper.className = 'px-3 py-2 border-t border-gray-100 dark:border-slate-700';

        var label = document.createElement('p');
        label.className  = 'text-xs font-medium text-gray-500 dark:text-slate-400 mb-2';
        label.textContent = 'New category';

        // Error message container (hidden until an API error occurs)
        var errorEl = document.createElement('p');
        errorEl.className  = 'text-xs text-red-600 dark:text-red-400 mb-1 hidden';
        errorEl.setAttribute('role', 'alert');

        var row = document.createElement('div');
        row.className = 'flex gap-2';

        // Icon input — short, for a single emoji character
        var iconInput = document.createElement('input');
        iconInput.type        = 'text';
        iconInput.placeholder = 'Icon';
        iconInput.maxLength   = 4; // Allow multi-byte emoji (up to 4 code units)
        iconInput.setAttribute('aria-label', 'Category icon (emoji)');
        iconInput.className = [
            'w-16 border border-gray-200 dark:border-slate-600 dark:bg-slate-700',
            'dark:text-white rounded px-2 py-1.5 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-teal-500'
        ].join(' ');

        // Name input
        var nameInput = document.createElement('input');
        nameInput.type        = 'text';
        nameInput.placeholder = 'Category name';
        nameInput.setAttribute('aria-label', 'Category name');
        nameInput.className = [
            'flex-1 border border-gray-200 dark:border-slate-600 dark:bg-slate-700',
            'dark:text-white rounded px-2 py-1.5 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-teal-500'
        ].join(' ');

        // Save button
        var saveBtn = document.createElement('button');
        saveBtn.type      = 'button';
        saveBtn.textContent = 'Save';
        saveBtn.className = [
            'px-3 py-1.5 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700',
            'rounded focus:outline-none focus:ring-2 focus:ring-teal-500 whitespace-nowrap'
        ].join(' ');

        // Save handler — POST to /api/categories and auto-select the new category
        saveBtn.addEventListener('mousedown', function(e) {
            e.preventDefault(); // Keep dropdown open during async save
        });
        saveBtn.addEventListener('click', function() {
            var name = nameInput.value.trim();
            var icon = iconInput.value.trim();

            if (!name) {
                errorEl.textContent = 'Name is required.';
                errorEl.classList.remove('hidden');
                nameInput.setAttribute('aria-invalid', 'true');
                nameInput.focus();
                return;
            }

            saveBtn.disabled    = true;
            saveBtn.textContent = 'Saving…';
            errorEl.classList.add('hidden');
            nameInput.removeAttribute('aria-invalid');

            fetch('/api/categories', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ name: name, icon: icon })
            })
            .then(function(res) {
                return res.json().then(function(data) {
                    return { ok: res.ok, data: data };
                });
            })
            .then(function(result) {
                if (!result.ok) {
                    // API returned an error (e.g. duplicate name)
                    var msg = (result.data && result.data.error) ? result.data.error : 'Failed to save.';
                    errorEl.textContent = msg;
                    errorEl.classList.remove('hidden');
                    nameInput.setAttribute('aria-invalid', 'true');
                    saveBtn.disabled    = false;
                    saveBtn.textContent = 'Save';
                    return;
                }

                // Add the new category to the local list so it appears in future searches
                var newCat = result.data;
                self.categories.push(newCat);

                // Auto-select the freshly created category and close the dropdown
                var label = (newCat.icon ? newCat.icon + ' ' : '') + newCat.name;
                self._selectCategory(newCat.id, label);
            })
            .catch(function() {
                errorEl.textContent = 'Network error. Please try again.';
                errorEl.classList.remove('hidden');
                saveBtn.disabled    = false;
                saveBtn.textContent = 'Save';
            });
        });

        // Prevent Enter from submitting the parent form — save category instead
        function handleAddFormKeydown(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveBtn.click();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                self._closeDropdown();
            }
        }
        nameInput.addEventListener('keydown', handleAddFormKeydown);
        iconInput.addEventListener('keydown', handleAddFormKeydown);

        row.appendChild(iconInput);
        row.appendChild(nameInput);
        row.appendChild(saveBtn);

        wrapper.appendChild(label);
        wrapper.appendChild(errorEl);
        wrapper.appendChild(row);

        // Focus the name input after the form is in the DOM (next tick)
        setTimeout(function() { nameInput.focus(); }, 0);

        return wrapper;
    };

    // _selectCategory commits a selection: sets hidden input value, updates text input,
    // and closes the dropdown.
    CategoryCombobox.prototype._selectCategory = function(id, displayText) {
        this.hiddenInput.value = id;
        this.textInput.value   = displayText;

        // Fire a native change event so HTMX or other listeners can react
        var event = new Event('change', { bubbles: true });
        this.hiddenInput.dispatchEvent(event);

        this._closeDropdown();
    };

    // selectById finds a category by UUID and selects it.
    // Used externally by the note-suggestion feature: el._combobox.selectById(id)
    CategoryCombobox.prototype.selectById = function(id) {
        if (!id) {
            this._selectCategory('', '');
            return;
        }
        for (var i = 0; i < this.categories.length; i++) {
            if (this.categories[i].id === id) {
                var cat   = this.categories[i];
                var label = (cat.icon ? cat.icon + ' ' : '') + cat.name;
                this._selectCategory(cat.id, label);
                return;
            }
        }
    };

    // _getOptionElements returns all currently rendered option elements in the listbox.
    // This excludes the inline add-form wrapper which is not a role="option" element.
    CategoryCombobox.prototype._getOptionElements = function() {
        return Array.prototype.slice.call(
            this.listbox.querySelectorAll('[role="option"]')
        );
    };

    // _updateActiveDescendant applies active styling to the focused option and scrolls
    // it into view. Updates aria-activedescendant on the text input.
    CategoryCombobox.prototype._updateActiveDescendant = function(options) {
        options.forEach(function(opt, i) {
            // Toggle the active background colour — keep selected style if it was selected
            var isSelected = opt.getAttribute('aria-selected') === 'true';
            var base       = 'px-3 py-2 text-sm cursor-pointer hover:bg-teal-50 dark:hover:bg-slate-700';
            if (i === this.activeIndex) {
                opt.className = base + ' bg-teal-50 dark:bg-slate-700' + (isSelected ? ' font-medium' : '');
            } else {
                opt.className = isSelected
                    ? base + ' bg-teal-50 dark:bg-slate-700 font-medium'
                    : base;
            }
        }, this);

        if (this.activeIndex >= 0 && options[this.activeIndex]) {
            var activeOpt = options[this.activeIndex];
            this.textInput.setAttribute('aria-activedescendant', activeOpt.id);
            // Scroll the focused option into view within the listbox
            activeOpt.scrollIntoView({ block: 'nearest' });
        } else {
            this.textInput.removeAttribute('aria-activedescendant');
        }
    };

    // Auto-initialize on DOMContentLoaded
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('[data-category-combobox]').forEach(function(el) {
            new CategoryCombobox(el);
        });
    });

    // Re-initialize after HTMX swaps new content into the page.
    // The guard (el._combobox check) prevents double-initialization of existing elements.
    document.addEventListener('htmx:afterSettle', function(e) {
        e.detail.target.querySelectorAll('[data-category-combobox]').forEach(function(el) {
            if (!el._combobox) new CategoryCombobox(el);
        });
    });

    return CategoryCombobox;
})();

// Expose on window for external selectById calls (e.g. note-suggestion feature).
window.CategoryCombobox = CategoryCombobox;
