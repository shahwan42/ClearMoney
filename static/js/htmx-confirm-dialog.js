// htmx-confirm-dialog.js — HTMX extension to replace browser confirm() with ConfirmDialog.
//
// Automatically intercepts hx-confirm attributes and shows the custom dialog.
// Works with all existing hx-confirm buttons without template changes.
//
// Usage: just include this script after htmx and confirm-dialog.js.
// Any button with hx-confirm="..." will use the custom dialog.

(function() {
    'use strict';

    htmx.defineExtension('confirm-dialog', {
        onEvent: function(name, evt) {
            if (name === 'htmx:confirm') {
                var question = evt.detail.question;
                var target = evt.detail.target;
                var elt = evt.detail.elt;

                evt.preventDefault();

                var title = 'Confirm action';
                var confirmText = 'Confirm';
                var confirmClass = 'bg-red-500 hover:bg-red-600 text-white';
                var cancelText = 'Cancel';

                if (elt.hasAttribute('hx-delete')) {
                    title = 'Confirm delete';
                    confirmText = 'Delete';
                }

                return ConfirmDialog.show({
                    title: title,
                    message: question,
                    confirmText: confirmText,
                    confirmClass: confirmClass,
                    cancelText: cancelText
                }).then(function(confirmed) {
                    if (confirmed) {
                        evt.detail.issueRequest(true);
                    }
                });
            }
        }
    });

    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('[hx-confirm]').forEach(function(elt) {
            if (!elt.hasAttribute('hx-ext')) {
                elt.setAttribute('hx-ext', 'confirm-dialog');
            } else if (elt.getAttribute('hx-ext').indexOf('confirm-dialog') === -1) {
                elt.setAttribute('hx-ext', elt.getAttribute('hx-ext') + ', confirm-dialog');
            }
        });
    });

    document.addEventListener('htmx:load', function(evt) {
        evt.detail.elt.querySelectorAll('[hx-confirm]').forEach(function(elt) {
            if (!elt.hasAttribute('hx-ext')) {
                elt.setAttribute('hx-ext', 'confirm-dialog');
            } else if (elt.getAttribute('hx-ext').indexOf('confirm-dialog') === -1) {
                elt.setAttribute('hx-ext', elt.getAttribute('hx-ext') + ', confirm-dialog');
            }
        });
    });
})();
