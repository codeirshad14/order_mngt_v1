"""Reports API — every report, as JSON, for a date range.

Authentication: every request must carry the key header.

    X-API-Key: <key>

The same key the product API uses. Create one in the admin under
Delaer -> API keys. Without one the API answers 401.

Two endpoints:

    GET /api/reports/
        the list of reports, so a caller can discover the slugs

    GET /api/reports/<slug>/?from=2026-04-01&to=2026-06-30
        that report's rows for those dates

Both ends of the range are optional: send only `from` for everything since a
date, only `to` for everything up to one, or neither for all time.

How the rows are produced, and why there is so little code here: a report is
not rebuilt for the API. This runs the report's own view — exactly as the CSV
download does — and reads the context that page was about to render. So the
JSON, the screen and the spreadsheet always agree, and a report added later
appears here with no work at all.

That also means the visibility rule is applied once, inside the report view:
the key's own user decides whose orders come back, so a dealer's key sees a
dealer's figures.
"""

from django.urls import resolve, reverse
from rest_framework import status
from rest_framework.response import Response

# the same key check the product API uses, so there is only one way in
from products.api import ApiKeyView

from . import exports
from .serilizer import ReportFilterSerializer, rows_as_json
from .views import REPORT_CARDS

# every response wraps its rows under this key
ENVELOPE = "report_details"


def find_card(slug):
    """The report with this slug, or None."""
    return next((c for c in REPORT_CARDS if c["slug"] == slug), None)


class ReportList(ApiKeyView):
    """GET /api/reports/ — which reports exist, and what to call them."""

    def get(self, request):
        reports = [
            {"slug": card["slug"], "name": card["name"]}
            for card in REPORT_CARDS
        ]
        return Response({"reports": reports, "count": len(reports)})


class ReportDetail(ApiKeyView):
    """GET /api/reports/<slug>/ — one report, for a date range."""

    def get(self, request, slug):
        card = find_card(slug)
        if card is None:
            return Response(
                {"errors": f"No report called {slug!r}.",
                 "reports": [c["slug"] for c in REPORT_CARDS]},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ---- 1. check what was asked for -------------------------------
        # on the wire the dates are ?from= and ?to=; the serializer calls them
        # date_from / date_to because `from` is a Python keyword
        params = request.query_params
        filters = ReportFilterSerializer(data={
            "date_from": params.get("from") or None,
            "date_to": params.get("to") or None,
            "q": params.get("q", ""),
            "dealer": params.get("dealer") or None,
            "sales": params.get("sales", ""),
        })
        if not filters.is_valid():
            return Response({"errors": filters.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        # ---- 2. run the report's own view ------------------------------
        context = self._run_report(request, card, filters.as_query())

        # ---- 3. shape what it produced ---------------------------------
        columns, rows = exports.table_for(slug, context)

        return Response({
            "report": card["slug"],
            "name": card["name"],
            "period": {
                "from": filters.validated_data.get("date_from"),
                "to": filters.validated_data.get("date_to"),
                "label": context["label"],
            },
            "count": len(rows),
            ENVELOPE: rows_as_json(columns, rows),
        })

    @staticmethod
    def _run_report(request, card, query):
        """Call the report view with our filter, and hand back its context.

        The report views are ordinary Django views: they read request.GET and
        request.user. We borrow the real HttpRequest underneath this API call,
        put our own query string on it, and let the view do the rest — so the
        period handling, the searching and the visibility rule are the ones the
        website already uses, not a second copy of them here.
        """
        http_request = request._request

        # request.user on the underlying HttpRequest is still the key's user,
        # set by ApiKeyAuthentication, which is who the report is run as
        http_request.GET = http_request.GET.copy()
        http_request.GET.clear()
        for key, value in query.items():
            http_request.GET[key] = value

        view = resolve(reverse(card["url"])).func
        return view(http_request).context_data
