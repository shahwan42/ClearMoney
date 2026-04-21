"""
Transaction URL patterns — page routes and HTMX partials.

Static paths come before UUID paths to avoid being swallowed
by the <uuid:tx_id> converter.
"""

from django.urls import path

from transactions import views

urlpatterns = [
    # --- Page Views ---
    path("transactions", views.transactions_list, name="transactions"),
    path("transactions/new", views.transaction_new, name="transaction-new"),
    path("batch-entry", views.batch_entry, name="batch-entry"),
    path("transfer/new", views.transfer_new_unified, name="transfer-new-unified"),
    # --- Legacy Redirects ---
    path("transfers/new", views.transfer_new),
    path("exchange/new", views.exchange_new),
    # --- HTMX Partials ---
    path(
        "transactions/list",
        views.transactions_list_partial,
        name="transaction-list-partial",
    ),
    path(
        "transactions/quick-form", views.quick_entry_form, name="transaction-quick-form"
    ),
    path(
        "transactions/quick-transfer-unified",
        views.quick_transfer_unified,
        name="transaction-quick-transfer-unified",
    ),
    path(
        "transactions/quick-transfer",
        views.quick_transfer_form,
        name="transaction-quick-transfer",
    ),
    path(
        "exchange/quick-form",
        views.quick_exchange_form,
        name="transaction-quick-exchange",
    ),
    path("transactions/batch", views.batch_create, name="transaction-batch-create"),
    path(
        "api/transactions/suggest-category",
        views.suggest_category,
        name="suggest-category",
    ),
    path("transactions/search", views.global_search, name="global-search"),
    path(
        "transactions/quick", views.quick_entry_create, name="transaction-quick-create"
    ),
    # --- Mutation Views ---
    path(
        "transactions/transfer",
        views.transfer_create,
        name="transaction-transfer-create",
    ),
    path(
        "transactions/exchange-submit",
        views.exchange_create,
        name="transaction-exchange-create",
    ),
    path("transactions/instapay-transfer", views.instapay_transfer_create),
    # --- Detail / Edit Views ---
    path(
        "transactions/edit/<uuid:tx_id>",
        views.transaction_edit_form,
        name="transaction-edit-form",
    ),
    path(
        "transactions/detail/<uuid:tx_id>",
        views.transaction_detail_sheet,
        name="transaction-detail-sheet",
    ),
    path(
        "transactions/row/<uuid:tx_id>", views.transaction_row, name="transaction-row"
    ),
    path(
        "transactions/<uuid:tx_id>/delete-attachment",
        views.transaction_delete_attachment,
        name="transaction-delete-attachment",
    ),
    path(
        "transactions/<uuid:tx_id>", views.transaction_detail, name="transaction-detail"
    ),
    # --- JSON API ---
    path(
        "api/transactions",
        views.api_transaction_list_create,
        name="api-transaction-list-create",
    ),
    path(
        "api/transactions/transfer",
        views.api_transaction_transfer,
        name="api-transaction-transfer",
    ),
    path(
        "api/transactions/exchange",
        views.api_transaction_exchange,
        name="api-transaction-exchange",
    ),
    path(
        "api/transactions/<uuid:tx_id>",
        views.api_transaction_detail,
        name="api-transaction-detail",
    ),
    path("sync/transactions", views.sync_transactions, name="sync-transactions"),
]
