// account-combobox.js — Searchable account dropdown with institution avatars.
// Auto-initializes on [data-account-combobox] elements.

var AccountCombobox = (function() {
    var instanceCount = 0;

    function formatBalance(value, currency) {
        var amount = Number(value || 0);
        try {
            return new Intl.NumberFormat(undefined, {
                style: 'currency',
                currency: currency || 'EGP',
                maximumFractionDigits: 2
            }).format(amount);
        } catch (e) {
            return amount.toFixed(2) + (currency ? ' ' + currency : '');
        }
    }

    function isImageIcon(icon) {
        return /\.(svg|png|jpe?g|webp)$/i.test(icon || '');
    }

    function fallbackInitial(account) {
        var raw = account.institution_name || account.name || '?';
        return raw.trim().charAt(0).toUpperCase() || '?';
    }

    function AccountCombobox(container) {
        if (container._accountCombobox) return;
        container._accountCombobox = this;

        instanceCount += 1;
        this.container = container;
        this.accounts = JSON.parse(container.getAttribute('data-accounts') || '[]');
        this.name = container.getAttribute('data-name') || 'account_id';
        this.selectedId = container.getAttribute('data-selected-id') || '';
        this.placeholder = container.getAttribute('data-placeholder') || 'Search accounts...';
        this.required = container.getAttribute('data-required') === 'true';
        this.inputId = container.getAttribute('data-input-id') || '';
        this.labelledBy = container.getAttribute('data-labelledby') || '';
        this.activeIndex = -1;
        this.isOpen = false;
        this.listboxId = 'account-listbox-' + instanceCount;
        this.optionIdPrefix = 'account-option-' + instanceCount + '-';

        this._buildDOM();
        this._attachEvents();

        if (this.selectedId) this.selectById(this.selectedId);
    }

    AccountCombobox.prototype._buildDOM = function() {
        this.container.style.position = 'relative';

        this.hiddenInput = document.createElement('input');
        this.hiddenInput.type = 'hidden';
        this.hiddenInput.name = this.name;
        this.hiddenInput.value = this.selectedId || '';
        if (this.required) this.hiddenInput.required = true;
        this.hiddenInput.setAttribute('data-validate', 'required');

        this.textInput = document.createElement('input');
        this.textInput.type = 'text';
        if (this.inputId) this.textInput.id = this.inputId;
        this.textInput.placeholder = this.placeholder;
        this.textInput.autocomplete = 'off';
        this.textInput.spellcheck = false;
        this.textInput.setAttribute('role', 'combobox');
        this.textInput.setAttribute('aria-expanded', 'false');
        this.textInput.setAttribute('aria-autocomplete', 'list');
        this.textInput.setAttribute('aria-controls', this.listboxId);
        this.textInput.setAttribute('aria-haspopup', 'listbox');
        if (this.required) this.textInput.required = true;
        if (this.labelledBy) this.textInput.setAttribute('aria-labelledby', this.labelledBy);
        this.textInput.className = [
            'w-full border border-gray-300 dark:border-slate-600',
            'dark:bg-slate-800 dark:text-slate-100 rounded-lg px-3 py-2.5 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-teal-500',
            'focus:ring-offset-2 dark:focus:ring-teal-400'
        ].join(' ');

        this.listbox = document.createElement('div');
        this.listbox.id = this.listboxId;
        this.listbox.setAttribute('role', 'listbox');
        this.listbox.className = [
            'absolute z-50 mt-1 w-full bg-white dark:bg-slate-800',
            'border border-gray-200 dark:border-slate-600 rounded-xl shadow-lg',
            'max-h-72 overflow-y-auto py-1'
        ].join(' ');
        this.listbox.style.display = 'none';

        this.container.appendChild(this.hiddenInput);
        this.container.appendChild(this.textInput);
        this.container.appendChild(this.listbox);
        this._syncValidity();
    };

    AccountCombobox.prototype._attachEvents = function() {
        var self = this;

        this.textInput.addEventListener('focus', function() {
            self._openDropdown();
        });

        this.textInput.addEventListener('click', function() {
            if (!self.isOpen) self._openDropdown();
        });

        this.textInput.addEventListener('input', function() {
            self.hiddenInput.value = '';
            self._syncSelectedDataset(null);
            self._syncValidity();
            self.hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
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
            if (!self.container.contains(e.target)) self._closeDropdown();
        });
    };

    AccountCombobox.prototype._openDropdown = function() {
        this.isOpen = true;
        this.activeIndex = -1;
        this._renderOptions();
        this.listbox.style.display = 'block';
        this.textInput.setAttribute('aria-expanded', 'true');
    };

    AccountCombobox.prototype._closeDropdown = function() {
        this.isOpen = false;
        this.listbox.style.display = 'none';
        this.textInput.setAttribute('aria-expanded', 'false');
        this.textInput.removeAttribute('aria-activedescendant');
    };

    AccountCombobox.prototype._renderOptions = function() {
        var self = this;
        var query = this.textInput.value.trim().toLowerCase();
        var filtered = this.accounts.filter(function(account) {
            var haystack = [
                account.name,
                account.currency,
                account.type,
                account.institution_name
            ].join(' ').toLowerCase();
            return haystack.indexOf(query) !== -1;
        });

        this.listbox.innerHTML = '';

        if (!filtered.length) {
            var empty = document.createElement('div');
            empty.className = 'px-3 py-3 text-sm text-gray-500 dark:text-slate-400';
            empty.textContent = 'No accounts found';
            this.listbox.appendChild(empty);
            return;
        }

        filtered.forEach(function(account, idx) {
            var optEl = self._makeOptionEl(
                self.optionIdPrefix + idx,
                account,
                account.id === self.hiddenInput.value
            );
            optEl.dataset.accountId = account.id;
            optEl.addEventListener('mousedown', function(e) {
                e.preventDefault();
                self._selectAccount(account);
            });
            self.listbox.appendChild(optEl);
        });
    };

    AccountCombobox.prototype._makeOptionEl = function(id, account, isSelected) {
        var el = document.createElement('div');
        el.id = id;
        el.setAttribute('role', 'option');
        el.setAttribute('aria-selected', isSelected ? 'true' : 'false');
        el.className = this._optionClass(isSelected, false);

        var avatar = document.createElement('span');
        avatar.className = [
            'w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center',
            'bg-slate-100 dark:bg-slate-700 text-xs font-bold text-slate-700 dark:text-slate-100',
            'overflow-hidden'
        ].join(' ');
        if (account.institution_color) avatar.style.backgroundColor = account.institution_color;

        if (isImageIcon(account.institution_icon)) {
            var img = document.createElement('img');
            img.src = '/static/img/institutions/' + account.institution_icon;
            img.alt = '';
            img.className = 'w-full h-full object-contain';
            avatar.appendChild(img);
        } else if (account.institution_icon) {
            avatar.textContent = account.institution_icon;
        } else {
            avatar.textContent = fallbackInitial(account);
            if (account.institution_color) avatar.style.color = '#fff';
        }

        var text = document.createElement('span');
        text.className = 'min-w-0 flex-1';

        var name = document.createElement('span');
        name.className = 'block truncate font-medium text-slate-800 dark:text-slate-100';
        name.textContent = account.name;

        var meta = document.createElement('span');
        meta.className = 'block truncate text-xs text-gray-500 dark:text-slate-400';
        var institution = account.institution_name ? account.institution_name + ' · ' : '';
        meta.textContent = institution + account.currency + ' · ' + formatBalance(account.current_balance, account.currency);

        text.appendChild(name);
        text.appendChild(meta);
        el.appendChild(avatar);
        el.appendChild(text);
        return el;
    };

    AccountCombobox.prototype._optionClass = function(isSelected, isActive) {
        var base = [
            'px-3 py-2 text-sm cursor-pointer flex items-center gap-3',
            'hover:bg-teal-50 dark:hover:bg-slate-700'
        ].join(' ');
        if (isSelected || isActive) {
            return base + ' bg-teal-50 dark:bg-slate-700';
        }
        return base;
    };

    AccountCombobox.prototype._selectAccount = function(account) {
        this.hiddenInput.value = account.id;
        this.textInput.value = account.name;
        this._syncSelectedDataset(account);
        this._syncValidity();

        var event = new CustomEvent('change', { bubbles: true, detail: { account: account } });
        this.hiddenInput.dispatchEvent(event);
        this._closeDropdown();
    };

    AccountCombobox.prototype._syncSelectedDataset = function(account) {
        this.hiddenInput.dataset.currency = account ? account.currency || '' : '';
        this.hiddenInput.dataset.accountName = account ? account.name || '' : '';
    };

    AccountCombobox.prototype._syncValidity = function() {
        if (!this.required) return;
        if (!this.hiddenInput.value && this.textInput.value.trim()) {
            this.textInput.setCustomValidity('Select an account from the list.');
        } else {
            this.textInput.setCustomValidity('');
        }
    };

    AccountCombobox.prototype.selectById = function(id) {
        if (!id) {
            this.hiddenInput.value = '';
            this.textInput.value = '';
            this._syncSelectedDataset(null);
            this._syncValidity();
            return;
        }
        for (var i = 0; i < this.accounts.length; i++) {
            if (this.accounts[i].id === id) {
                this._selectAccount(this.accounts[i]);
                return;
            }
        }
    };

    AccountCombobox.prototype._getOptionElements = function() {
        return Array.prototype.slice.call(this.listbox.querySelectorAll('[role="option"]'));
    };

    AccountCombobox.prototype._updateActiveDescendant = function(options) {
        options.forEach(function(opt, i) {
            var isSelected = opt.getAttribute('aria-selected') === 'true';
            opt.className = this._optionClass(isSelected, i === this.activeIndex);
        }, this);

        if (this.activeIndex >= 0 && options[this.activeIndex]) {
            var activeOpt = options[this.activeIndex];
            this.textInput.setAttribute('aria-activedescendant', activeOpt.id);
            activeOpt.scrollIntoView({ block: 'nearest' });
        } else {
            this.textInput.removeAttribute('aria-activedescendant');
        }
    };

    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('[data-account-combobox]').forEach(function(el) {
            new AccountCombobox(el);
        });
    });

    document.addEventListener('htmx:afterSettle', function(e) {
        e.detail.target.querySelectorAll('[data-account-combobox]').forEach(function(el) {
            if (!el._accountCombobox) new AccountCombobox(el);
        });
    });

    return AccountCombobox;
})();

window.AccountCombobox = AccountCombobox;
