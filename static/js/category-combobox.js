// category-combobox.js — Searchable category dropdown replacing native <select>.
// Auto-initializes on [data-category-combobox] elements.
// Follows the same IIFE + prototype pattern as bottom-sheet.js.
//
// Usage:
//   <div data-category-combobox
//        data-categories='[{"id":"uuid","name":"Food","icon":"🍕","type":"expense"},...]'
//        data-name="category_id"
//        data-selected-id="optional-uuid"
//        data-filter-type="expense"   -- optional: "expense"|"income" to filter shown categories
//        data-placeholder="Search categories..."
//        data-allow-empty="true">
//   </div>
//
// Programmatic API:
//   el._combobox.selectById('uuid')           — select by ID
//   el._combobox.setFilterType('income')      — switch visible category type
//   el._combobox.addCategory(cat)             — add a category to the local list

var CategoryCombobox = (function() {
    var instanceCount = 0;

    // Track the "active" combobox — the one that last opened its dropdown.
    // Used to route category:created events to the right combobox.
    var activeCombobox = null;

    function CategoryCombobox(container) {
        if (container._combobox) return;
        container._combobox = this;

        instanceCount += 1;
        var uid = instanceCount;

        this.container   = container;
        this.categories  = JSON.parse(container.getAttribute('data-categories') || '[]');
        this.name        = container.getAttribute('data-name') || 'category_id';
        this.selectedId  = container.getAttribute('data-selected-id') || '';
        this.placeholder = container.getAttribute('data-placeholder') || 'Search categories...';
        this.allowEmpty  = container.getAttribute('data-allow-empty') === 'true';
        this.filterType  = container.getAttribute('data-filter-type') || '';

        this.activeIndex    = -1;
        this.isOpen         = false;
        this.listboxId      = 'category-listbox-' + uid;
        this.optionIdPrefix = 'category-option-' + uid + '-';

        this._buildDOM();
        this._attachEvents();

        if (this.selectedId) {
            this.selectById(this.selectedId);
        }
    }

    CategoryCombobox.prototype._buildDOM = function() {
        this.container.style.position = 'relative';

        this.hiddenInput = document.createElement('input');
        this.hiddenInput.type  = 'hidden';
        this.hiddenInput.name  = this.name;
        this.hiddenInput.value = this.selectedId || '';

        this.textInput = document.createElement('input');
        this.textInput.type         = 'text';
        this.textInput.setAttribute('data-testid', (this.container.id || 'category') + '-input');
        this.textInput.placeholder  = this.placeholder;
        this.textInput.autocomplete = 'off';
        this.textInput.maxLength    = 100;
        this.textInput.spellcheck   = false;
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

    CategoryCombobox.prototype._attachEvents = function() {
        var self = this;

        this.textInput.addEventListener('focus', function() {
            activeCombobox = self;
            self._openDropdown();
        });

        this.textInput.addEventListener('click', function() {
            activeCombobox = self;
            if (!self.isOpen) self._openDropdown();
        });

        this.textInput.addEventListener('input', function() {
            self._renderOptions();
            if (!self.isOpen) self._openDropdown();
        });

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

        document.addEventListener('mousedown', function(e) {
            if (!self.container.contains(e.target)) {
                self._closeDropdown();
            }
        });
    };

    CategoryCombobox.prototype._openDropdown = function() {
        this.isOpen = true;
        this.activeIndex = -1;
        this._renderOptions();
        this.listbox.style.display = 'block';
        this.textInput.setAttribute('aria-expanded', 'true');
    };

    CategoryCombobox.prototype._closeDropdown = function() {
        this.isOpen = false;
        this.listbox.style.display = 'none';
        this.textInput.setAttribute('aria-expanded', 'false');
        this.textInput.removeAttribute('aria-activedescendant');
    };

    CategoryCombobox.prototype._filteredCategories = function() {
        var self = this;
        var query = this.textInput.value.trim().toLowerCase();
        return this.categories.filter(function(cat) {
            var typeMatch = !self.filterType || cat.type === self.filterType;
            var nameMatch = cat.name.toLowerCase().indexOf(query) !== -1;
            return typeMatch && nameMatch;
        });
    };

    CategoryCombobox.prototype._renderOptions = function() {
        var self = this;
        var filtered = this._filteredCategories();

        this.listbox.innerHTML = '';

        if (this.allowEmpty) {
            var noneEl = this._makeOptionEl(
                this.optionIdPrefix + 'none',
                '— None',
                '',
                this.hiddenInput.value === ''
            );
            noneEl.addEventListener('mousedown', function(e) {
                e.preventDefault();
                self._selectCategory('', '');
            });
            this.listbox.appendChild(noneEl);
        }

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

        // "+ Add new category" — opens bottom sheet
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
            self._closeDropdown();
            activeCombobox = self;
            var type = self.filterType || 'expense';
            if (window.BottomSheet) {
                BottomSheet.open('new-category', { url: '/settings/categories/new-form?type=' + type });
            }
        });
        this.listbox.appendChild(addBtn);
    };

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

    CategoryCombobox.prototype._selectCategory = function(id, displayText) {
        this.hiddenInput.value = id;
        this.textInput.value   = displayText;

        var event = new Event('change', { bubbles: true });
        this.hiddenInput.dispatchEvent(event);

        this._closeDropdown();
    };

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

    // Add a new category to the local list and optionally auto-select it.
    CategoryCombobox.prototype.addCategory = function(cat, autoSelect) {
        this.categories.push(cat);
        if (autoSelect) {
            var label = (cat.icon ? cat.icon + ' ' : '') + cat.name;
            this._selectCategory(cat.id, label);
        }
    };

    // Switch the visible category type filter. Clears selection if current
    // selected category doesn't match the new type.
    CategoryCombobox.prototype.setFilterType = function(type) {
        this.filterType = type;
        // If the currently selected category doesn't match the new type, clear it.
        if (this.hiddenInput.value) {
            var selected = this.categories.find(function(c) { return c.id === this.hiddenInput.value; }, this);
            if (selected && selected.type && selected.type !== type) {
                this._selectCategory('', '');
            }
        }
        if (this.isOpen) {
            this._renderOptions();
        }
    };

    CategoryCombobox.prototype._getOptionElements = function() {
        return Array.prototype.slice.call(
            this.listbox.querySelectorAll('[role="option"]')
        );
    };

    CategoryCombobox.prototype._updateActiveDescendant = function(options) {
        options.forEach(function(opt, i) {
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
            activeOpt.scrollIntoView({ block: 'nearest' });
        } else {
            this.textInput.removeAttribute('aria-activedescendant');
        }
    };

    // Listen for category:created events from the bottom sheet.
    // Auto-selects in the active combobox if the type matches its filter.
    document.addEventListener('category:created', function(e) {
        var cat = e.detail;
        if (!cat || !cat.id) return;

        // Add to all comboboxes on the page
        document.querySelectorAll('[data-category-combobox]').forEach(function(el) {
            if (el._combobox) {
                var isDuplicate = el._combobox.categories.some(function(c) { return c.id === cat.id; });
                if (!isDuplicate) {
                    el._combobox.categories.push(cat);
                }
            }
        });

        // Auto-select in the combobox that triggered the sheet open
        if (activeCombobox) {
            var typeMatch = !activeCombobox.filterType || cat.type === activeCombobox.filterType;
            if (typeMatch) {
                var label = (cat.icon ? cat.icon + ' ' : '') + cat.name;
                activeCombobox._selectCategory(cat.id, label);
            }
            activeCombobox = null;
        }
    });

    function init(root) {
        root = root || document;
        root.querySelectorAll('[data-category-combobox]').forEach(function(el) {
            if (!el._combobox) new CategoryCombobox(el);
        });
    }

    document.addEventListener('DOMContentLoaded', function() { init(); });
    document.addEventListener('htmx:afterSettle', function(e) { init(e.detail.target); });

    return { init: init };
})();

window.CategoryCombobox = CategoryCombobox;
