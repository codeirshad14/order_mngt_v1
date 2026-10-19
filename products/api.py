"""Product API for the mobile app and Tally.

Authentication: every request must carry the key header.

    X-API-Key: <key>

Create a key in the admin under Delaer -> API keys. Without one the API
answers 401.

Matching: a product is found by its **name**. POST a name that already
exists and that product is updated; POST a new name and a product is
created. That is what makes a sync safe to run twice.
"""

from django.db import IntegrityError
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from delaer.authentication import ApiKeyAuthentication

from .models import Product
from .serilizers import ProductSerializer

# every response wraps its products under this key
ENVELOPE = "product_details"


class ApiKeyView(APIView):
    """Shared authentication: X-API-Key on every request."""

    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [IsAuthenticated]


def find_by_name(name):
    """The product with this name, or None.

    Case is ignored, so "app 1" finds "APP 1". Name is not a unique column,
    so if two products share one the oldest wins.
    """
    name = (name or "").strip()
    if not name:
        return None
    return Product.objects.filter(name__iexact=name).order_by("pk").first()


class ProductListCreate(ApiKeyView):
    """GET  /api/products/   — list
    POST /api/products/   — create, or update when the name already exists
    """

    def get(self, request):
        products = Product.objects.select_related("brand", "unit")

        if request.query_params.get("active") == "true":
            products = products.filter(is_active=True)

        search = request.query_params.get("q")
        if search:
            products = products.filter(name__icontains=search)

        data = ProductSerializer(products, many=True).data
        return Response({ENVELOPE: data, "count": len(data)})

    def post(self, request):
        saved = []
        errors = []

        for index, row in enumerate(self._rows(request.data)):
            name = (row or {}).get("name")
            product = find_by_name(name)          # found -> update, else create

            serializer = ProductSerializer(product, data=row or {}, partial=bool(product))

            if not serializer.is_valid():
                errors.append({"index": index, "name": name, "errors": serializer.errors})
                continue

            try:
                serializer.save()
            except (IntegrityError, ValueError) as exc:
                # one bad row is reported; the rest of the sync still lands
                errors.append({"index": index, "name": name, "errors": str(exc)})
            else:
                saved.append(serializer.data)

        body = {ENVELOPE: saved, "saved": len(saved), "failed": len(errors)}
        if errors:
            body["errors"] = errors

        # 400 only when nothing at all got through
        code = status.HTTP_400_BAD_REQUEST if errors and not saved else status.HTTP_200_OK
        return Response(body, status=code)

    @staticmethod
    def _rows(payload):
        """Accept one object, a bare list, or {"product_details": [...]}."""
        if isinstance(payload, dict) and ENVELOPE in payload:
            payload = payload[ENVELOPE]
        return payload if isinstance(payload, list) else [payload]


class ProductDetail(ApiKeyView):
    """GET / PUT / PATCH  /api/products/<name>/"""

    def get_product(self, lookup):
        product = find_by_name(lookup)
        if product is None:
            raise Http404(f"No product named {lookup}.")
        return product

    def get(self, request, lookup):
        return Response(ProductSerializer(self.get_product(lookup)).data)

    def put(self, request, lookup):
        return self._save(request, lookup, partial=False)

    def patch(self, request, lookup):
        return self._save(request, lookup, partial=True)

    def _save(self, request, lookup, partial):
        serializer = ProductSerializer(
            self.get_product(lookup), data=request.data, partial=partial
        )
        if not serializer.is_valid():
            return Response({"errors": serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer.save()
        except (IntegrityError, ValueError) as exc:
            return Response({"errors": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data)
