// form-validation.js — Inline form validation with accessibility support.
// Auto-initializes on forms with [data-validate] attributes.
//
// Usage:
//   <input data-validate="required" ...>
//   <input data-validate="min:0.01" ...>
//   <input data-validate="maxlength:100" ...>
//   <input data-validate="date:not-future" ...>
//   <input data-validate="required,min:0.01" ...>
//
// Features:
// - Validates on blur
// - Shows field-specific error messages
// - Sets aria-invalid="true" on invalid fields
// - Links error messages via aria-describedby
// - Uses role="alert" for screen reader announcement
// - Character count for maxlength fields
// - Does not block submission (server validation authoritative)

var FormValidation = (function() {
    'use strict';

    // Error message templates
    var MESSAGES = {
        required: 'This field is required',
        min: 'Amount must be greater than 0',
        maxlength: 'Maximum {max} characters allowed',
        date_not_future: 'Date cannot be in the future',
        email: 'Please enter a valid email address'
    };

    // Parse validation rules from data-validate attribute
    function parseRules(value) {
        if (!value) return [];
        return value.split(',').map(function(rule) {
            rule = rule.trim();
            if (rule.indexOf(':') !== -1) {
                var parts = rule.split(':');
                return { name: parts[0], value: parts[1] };
            }
            return { name: rule, value: null };
        });
    }

    // Validate a single field against its rules
    function validateField(field) {
        var rules = parseRules(field.getAttribute('data-validate'));
        var value = field.value.trim();
        var errors = [];

        for (var i = 0; i < rules.length; i++) {
            var rule = rules[i];
            var error = null;

            switch (rule.name) {
                case 'required':
                    if (!value) {
                        error = MESSAGES.required;
                    }
                    break;
                case 'min':
                    if (value && parseFloat(value) < parseFloat(rule.value)) {
                        error = MESSAGES.min;
                    }
                    break;
                case 'maxlength':
                    if (value.length > parseInt(rule.value, 10)) {
                        error = MESSAGES.maxlength.replace('{max}', rule.value);
                    }
                    break;
                case 'date':
                    if (rule.value === 'not-future' && value) {
                        var fieldDate = new Date(value);
                        var today = new Date();
                        today.setHours(0, 0, 0, 0);
                        if (fieldDate > today) {
                            error = MESSAGES.date_not_future;
                        }
                    }
                    break;
                case 'email':
                    if (value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
                        error = MESSAGES.email;
                    }
                    break;
            }

            if (error) {
                errors.push(error);
            }
        }

        return errors;
    }

    // Get or create error message container for a field
    function getOrCreateErrorContainer(field, form) {
        var errorId = field.id + '-error';
        var errorEl = document.getElementById(errorId);

        if (!errorEl) {
            errorEl = document.createElement('div');
            errorEl.id = errorId;
            errorEl.setAttribute('role', 'alert');
            errorEl.className = 'text-red-500 dark:text-red-400 text-xs mt-1 hidden';
            field.parentNode.insertBefore(errorEl, field.nextSibling);
        }

        return errorEl;
    }

    // Get or create character count container for maxlength fields
    function getOrCreateCharCount(field, form) {
        var countId = field.id + '-count';
        var countEl = document.getElementById(countId);

        if (!countEl) {
            var maxlength = field.getAttribute('maxlength');
            if (!maxlength) return null;

            countEl = document.createElement('div');
            countEl.id = countId;
            countEl.className = 'text-xs text-gray-400 dark:text-slate-500 mt-1 text-right';
            field.parentNode.insertBefore(countEl, field.nextSibling);
        }

        return countEl;
    }

    // Update character count display
    function updateCharCount(field) {
        var countEl = getOrCreateCharCount(field);
        if (!countEl) return;

        var current = field.value.length;
        var max = parseInt(field.getAttribute('maxlength'), 10);
        countEl.textContent = current + '/' + max;

        // Visual warning when approaching limit
        if (current > max * 0.9) {
            countEl.classList.add('text-amber-500');
        } else {
            countEl.classList.remove('text-amber-500');
        }
    }

    // Show validation error for a field
    function showError(field, message) {
        var form = field.closest('form');
        var errorEl = getOrCreateErrorContainer(field, form);

        field.setAttribute('aria-invalid', 'true');
        field.setAttribute('aria-describedby', errorEl.id);
        errorEl.textContent = message;
        errorEl.classList.remove('hidden');
    }

    // Clear validation error for a field
    function clearError(field) {
        var form = field.closest('form');
        var errorId = field.id + '-error';
        var errorEl = document.getElementById(errorId);

        field.removeAttribute('aria-invalid');
        field.removeAttribute('aria-describedby');
        if (errorEl) {
            errorEl.classList.add('hidden');
            errorEl.textContent = '';
        }
    }

    // Handle blur event on a field
    function handleBlur(field) {
        var errors = validateField(field);

        if (errors.length > 0) {
            showError(field, errors[0]);
        } else {
            clearError(field);
        }

        // Update character count if applicable
        if (field.getAttribute('maxlength')) {
            updateCharCount(field);
        }
    }

    // Initialize validation for a form
    function initForm(form) {
        var fields = form.querySelectorAll('[data-validate]');

        for (var i = 0; i < fields.length; i++) {
            var field = fields[i];

            // Ensure field has an ID for error container linking
            if (!field.id) {
                field.id = 'field-' + Math.random().toString(36).substr(2, 9);
            }

            // Attach blur handler
            field.addEventListener('blur', function() {
                handleBlur(this);
            });

            // Clear error on input (progressive correction)
            field.addEventListener('input', function() {
                if (this.getAttribute('aria-invalid') === 'true') {
                    var errors = validateField(this);
                    if (errors.length === 0) {
                        clearError(this);
                    }
                }

                // Update character count on every keystroke
                if (this.getAttribute('maxlength')) {
                    updateCharCount(this);
                }
            });

            // Initialize character count if maxlength
            if (field.getAttribute('maxlength')) {
                updateCharCount(field);
            }
        }
    }

    // Auto-initialize on DOM ready
    function init() {
        var forms = document.querySelectorAll('form');

        for (var i = 0; i < forms.length; i++) {
            var form = forms[i];
            var hasValidation = form.querySelector('[data-validate]');
            if (hasValidation) {
                initForm(form);
            }
        }
    }

    // Re-initialize when HTMX swaps in new content (e.g. BottomSheet forms)
    document.addEventListener('htmx:afterSettle', function(e) {
        var target = e.detail && e.detail.target;
        if (!target) return;
        var forms = target.querySelectorAll ? target.querySelectorAll('form') : [];
        for (var i = 0; i < forms.length; i++) {
            if (forms[i].querySelector('[data-validate]')) {
                initForm(forms[i]);
            }
        }
        // Also handle if the target itself is a form
        if (target.tagName === 'FORM' && target.querySelector('[data-validate]')) {
            initForm(target);
        }
    });

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Public API
    return {
        init: init,
        initForm: initForm,
        validateField: validateField,
        handleBlur: handleBlur
    };
})();
