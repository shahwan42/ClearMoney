"""
Transactions URL configuration.

Port of Go's transaction routes from router.go (lines 301-345).
Handles all /transactions/*, /transfers/*, /exchange/*, /batch-entry,
/fawry-cashout, and /sync/transactions routes.

Static paths MUST come before <uuid:id> to avoid being swallowed.
"""

from django.urls import path

from transactions import views

urlpatterns = [
    # --- Transaction pages ---
    path("transactions", views.transactions_list, name="transactions"),
    # Static sub-paths MUST come before <uuid:id>
    path("transactions/list", views.transactions_list_partial, name="transactions-list"),
    path("transactions/new", views.transaction_new, name="transaction-new"),
    path("transactions/quick-form", views.quick_entry_form, name="quick-entry-form"),
    path("transactions/quick", views.quick_entry_create, name="quick-entry-create"),
    path("transactions/quick-transfer", views.quick_transfer_form, name="quick-transfer-form"),
    path("transactions/transfer", views.transfer_create, name="transfer-create"),
    path("transactions/instapay-transfer", views.instapay_transfer_create, name="instapay-transfer"),
    path("transactions/exchange-submit", views.exchange_create, name="exchange-create"),
    path("transactions/fawry-cashout", views.fawry_cashout_create, name="fawry-cashout-create"),
    path("transactions/batch", views.batch_create, name="batch-create"),
    # UUID sub-paths
    path("transactions/edit/<uuid:tx_id>", views.transaction_edit_form, name="transaction-edit"),
    path("transactions/row/<uuid:tx_id>", views.transaction_row, name="transaction-row"),
    path("transactions/<uuid:tx_id>", views.transaction_detail, name="transaction-detail"),
    # --- Transfer pages ---
    path("transfers/new", views.transfer_new, name="transfer-new"),
    # --- Exchange pages ---
    path("exchange/new", views.exchange_new, name="exchange-new"),
    path("exchange/quick-form", views.quick_exchange_form, name="quick-exchange-form"),
    # --- Fawry ---
    path("fawry-cashout", views.fawry_cashout, name="fawry-cashout"),
    # --- Batch entry ---
    path("batch-entry", views.batch_entry, name="batch-entry"),
    # --- Sync API ---
    path("sync/transactions", views.sync_transactions, name="sync-transactions"),
    # --- Category suggestion API ---
    path("api/transactions/suggest-category", views.suggest_category, name="suggest-category"),
    # --- JSON API routes (static paths before UUID) ---
    path("api/transactions/transfer", views.api_transaction_transfer, name="api-transaction-transfer"),
    path("api/transactions/exchange", views.api_transaction_exchange, name="api-transaction-exchange"),
    path("api/transactions", views.api_transaction_list_create, name="api-transactions"),
    path("api/transactions/<uuid:tx_id>", views.api_transaction_detail, name="api-transaction-detail"),
]
