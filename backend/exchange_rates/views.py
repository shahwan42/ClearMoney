"""
Exchange rate views — page handler for /exchange-rates.

Like Laravel's ExchangeRateController — read-only list view.
"""

import logging

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from exchange_rates.services import ExchangeRateService

logger = logging.getLogger(__name__)


@general_rate
@require_http_methods(["GET"])
def exchange_rates_page(request: AuthenticatedRequest) -> HttpResponse:
    """GET /exchange-rates — render the exchange rate history page.

    Shows a reverse-chronological list of logged USD/EGP rates.
    """
    logger.info("page viewed: exchange-rates, user=%s", request.user_email)
    svc = ExchangeRateService(request.tz)
    rates = svc.get_all()

    return render(
        request,
        "exchange_rates/exchange_rates.html",
        {
            "rates": rates,
            "active_tab": "reports",
        },
    )
