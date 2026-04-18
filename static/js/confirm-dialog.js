// confirm-dialog.js — Custom confirmation dialog replacing browser confirm().
// Provides accessible, branded confirmation dialogs with focus trap and keyboard support.
//
// Usage:
//   ConfirmDialog.show({
//     title: 'Delete transaction',
//     message: 'Are you sure you want to delete this transaction?',
//     confirmText: 'Delete',
//     confirmClass: 'bg-red-500 hover:bg-red-600',
//     cancelText: 'Cancel'
//   }).then(confirmed => {
//     if (confirmed) { /* proceed */ }
//   });

var ConfirmDialog = (function() {
    var overlay, dialog, dialogTitle, dialogMessage, confirmBtn, cancelBtn;
    var previousFocus = null;
    var resolvePromise = null;

    function init() {
        overlay = document.getElementById('confirm-dialog-overlay');
        dialog = document.getElementById('confirm-dialog');
        dialogTitle = document.getElementById('confirm-dialog-title');
        dialogMessage = document.getElementById('confirm-dialog-message');
        confirmBtn = document.getElementById('confirm-dialog-confirm');
        cancelBtn = document.getElementById('confirm-dialog-cancel');

        if (!overlay || !dialog) return;

        overlay.addEventListener('click', function() {
            close(false);
        });

        if (cancelBtn) {
            cancelBtn.addEventListener('click', function() {
                close(false);
            });
        }

        if (confirmBtn) {
            confirmBtn.addEventListener('click', function() {
                close(true);
            });
        }
    }

    function open(options) {
        return new Promise(function(resolve) {
            resolvePromise = resolve;

            previousFocus = document.activeElement;

            if (overlay) overlay.classList.remove('hidden');
            if (dialog) {
                dialog.classList.remove('hidden');
                dialog.classList.add('translate-y-full');
                dialog.offsetHeight;
                dialog.classList.remove('translate-y-full');
                dialog.classList.add('translate-y-0');
            }

            if (dialogTitle && options.title) {
                dialogTitle.textContent = options.title;
            }

            if (dialogMessage && options.message) {
                dialogMessage.textContent = options.message;
            }

            if (confirmBtn) {
                confirmBtn.textContent = options.confirmText || 'Confirm';
                confirmBtn.className = 'w-full py-3 px-4 rounded-lg font-medium transition-colors ' + (options.confirmClass || 'bg-red-500 hover:bg-red-600 text-white');
            }

            if (cancelBtn) {
                cancelBtn.textContent = options.cancelText || 'Cancel';
            }

            setTimeout(function() {
                if (confirmBtn) confirmBtn.focus();
            }, 300);
        });
    }

    function close(confirmed) {
        if (dialog) {
            dialog.classList.remove('translate-y-0');
            dialog.classList.add('translate-y-full');
        }

        if (overlay) overlay.classList.add('hidden');

        setTimeout(function() {
            if (dialog) dialog.classList.add('hidden');
        }, 300);

        if (previousFocus && typeof previousFocus.focus === 'function') {
            previousFocus.focus();
        }

        if (resolvePromise) {
            resolvePromise(confirmed);
            resolvePromise = null;
        }
    }

    function isOpen() {
        return overlay && !overlay.classList.contains('hidden');
    }

    document.addEventListener('keydown', function(e) {
        if (!isOpen()) return;

        if (e.key === 'Escape') {
            close(false);
            return;
        }

        if (e.key === 'Tab') {
            var focusable = dialog.querySelectorAll('button:not([disabled]), [tabindex]:not([tabindex="-1"])');
            if (focusable.length === 0) return;

            var first = focusable[0];
            var last = focusable[focusable.length - 1];

            if (e.shiftKey) {
                if (document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                }
            } else {
                if (document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        }
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    document.addEventListener('htmx:afterSettle', init);

    return {
        show: open,
        close: close,
        isOpen: isOpen,
        init: init
    };
})();
