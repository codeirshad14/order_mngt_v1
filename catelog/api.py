"""Catelog and New Arrival API, built the same way as the product API.

Authentication: every request must carry the key header.

    X-API-Key: <key>

Create a key in the admin under Delaer -> API keys. Without one the API
answers 401. It is the same key the product API uses.

Matching: a group is found by its **name**. POST a name that already exists
and that group is updated; POST a new name and one is created. That is what
makes a sync safe to run twice.

Each response wraps its rows under a parent name:

    {"catelog":    [ ... ]}      for catelogs
    {"newarrival": [ ... ]}      for new arrivals

Both take the same shape:

    {"catelog": [
        {"name": "Summer Range", "products": ["APP 1", "Bottle Plus 66"]}
    ]}
"""

from django.db import IntegrityError
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response

# the same key check the product API uses, so there is only one way in
from products.api import ApiKeyView

from .models import Catelog, NewArrival
from .serilizer import CatelogSerializer, NewArrivalSerializer

# the parent name each kind of row is wrapped under
CATELOG = "catelog"
NEWARRIVAL = "newarrival"


def find_by_name(model, name):
    """The group with this name, or None. Case is ignored."""
    name = (name or "").strip()
    if not name:
        return None
    return model.objects.filter(name__iexact=name).order_by("pk").first()


class GroupListCreate(ApiKeyView):
    """GET  — list
    POST — create, or update when the name already exists

    `model`, `serializer_class` and `envelope` are set by the two views at the
    foot of this file; everything else is shared.
    """

    model = None
    serializer_class = None
    envelope = None

    def get(self, request):
        groups = self.model.objects.prefetch_related("products")

        search = request.query_params.get("q")
        if search:
            groups = groups.filter(name__icontains=search)

        data = self.serializer_class(groups, many=True).data
        return Response({self.envelope: data, "count": len(data)})

    def post(self, request):
        saved = []
        errors = []

        for index, row in enumerate(self._rows(request.data)):
            name = (row or {}).get("name")
            group = find_by_name(self.model, name)     # found -> update, else create

            serializer = self.serializer_class(
                group, data=row or {}, partial=bool(group)
            )

            if not serializer.is_valid():
                errors.append({"index": index, "name": name,
                               "errors": serializer.errors})
                continue

            try:
                serializer.save()
            except (IntegrityError, ValueError) as exc:
                # one bad row is reported; the rest of the sync still lands
                errors.append({"index": index, "name": name, "errors": str(exc)})
            else:
                saved.append(serializer.data)

        body = {self.envelope: saved, "saved": len(saved), "failed": len(errors)}
        if errors:
            body["errors"] = errors

        # 400 only when nothing at all got through
        code = status.HTTP_400_BAD_REQUEST if errors and not saved else status.HTTP_200_OK
        return Response(body, status=code)

    def _rows(self, payload):
        """Accept one object, a bare list, or {"<envelope>": [...]}."""
        if isinstance(payload, dict) and self.envelope in payload:
            payload = payload[self.envelope]
        return payload if isinstance(payload, list) else [payload]


class GroupDetail(ApiKeyView):
    """GET / PUT / PATCH on one group, looked up by name."""

    model = None
    serializer_class = None

    def get_group(self, lookup):
        group = find_by_name(self.model, lookup)
        if group is None:
            raise Http404(f"No {self.model._meta.verbose_name} named {lookup}.")
        return group

    def get(self, request, lookup):
        return Response(self.serializer_class(self.get_group(lookup)).data)

    def put(self, request, lookup):
        return self._save(request, lookup, partial=False)

    def patch(self, request, lookup):
        return self._save(request, lookup, partial=True)

    def _save(self, request, lookup, partial):
        serializer = self.serializer_class(
            self.get_group(lookup), data=request.data, partial=partial
        )
        if not serializer.is_valid():
            return Response({"errors": serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer.save()
        except (IntegrityError, ValueError) as exc:
            return Response({"errors": str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data)


# ------------------------------------------------------------- the four views


class CatelogListCreate(GroupListCreate):
    model = Catelog
    serializer_class = CatelogSerializer
    envelope = CATELOG


class CatelogDetail(GroupDetail):
    model = Catelog
    serializer_class = CatelogSerializer


class NewArrivalListCreate(GroupListCreate):
    model = NewArrival
    serializer_class = NewArrivalSerializer
    envelope = NEWARRIVAL


class NewArrivalDetail(GroupDetail):
    model = NewArrival
    serializer_class = NewArrivalSerializer
