"""Reports API serializer.

Two jobs, and they are deliberately small:

1. ReportFilterSerializer   — check what the caller asked for (a date range,
                              and optionally a search word, a dealer or a
                              salesman), and turn it into the same query string
                              the report pages already understand.

2. rows_as_json()           — turn a report's (columns, rows) into a list of
                              JSON objects.

Nothing here knows what any individual report contains. The reports already
produce their own columns and rows for the CSV/Excel/PDF downloads, and the API
reuses exactly that, so a new report needs no changes in this file.
"""

import re
from datetime import date
from decimal import Decimal

from rest_framework import serializers


class ReportFilterSerializer(serializers.Serializer):
    """What an API caller may ask for.

    The two date fields are named date_from / date_to here because `from` is a
    Python keyword and cannot be an attribute name. On the wire they stay
    ?from= and ?to=, the same as the website uses — api.py does that mapping.
    """

    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)

    # the same three narrowing options the report pages offer
    q = serializers.CharField(required=False, allow_blank=True)
    dealer = serializers.IntegerField(required=False, allow_null=True)
    sales = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        start, end = data.get("date_from"), data.get("date_to")
        if start and end and start > end:
            raise serializers.ValidationError(
                {"from": "The start date is after the end date."}
            )
        return data

    def as_query(self):
        """The validated filter, as the query string a report view expects.

        The report pages read a `period` plus its dates. `range` is the period
        that means "these two dates", and it accepts either end on its own, so
        a caller can ask for everything since a date without inventing an end.
        With no dates at all the report covers all time, which is the same
        thing the page does.
        """
        data = self.validated_data
        query = {"period": "range"}

        if data.get("date_from"):
            query["from"] = data["date_from"].isoformat()
        if data.get("date_to"):
            query["to"] = data["date_to"].isoformat()

        if data.get("q"):
            query["q"] = data["q"]
        if data.get("dealer"):
            query["dealer"] = str(data["dealer"])
        if data.get("sales"):
            query["sales"] = data["sales"]

        return query


def as_key(column):
    """A column heading turned into a JSON key.

    "Order No" -> "order_no", "CGST %" -> "cgst_pct", "Raised By" -> "raised_by".
    Done so the JSON reads like JSON rather than like a spreadsheet header.

    "#" is the ranking column on the Top reports. Stripped of punctuation it
    would leave nothing at all, so it is named here rather than falling through
    to the column_N fallback below.
    """
    column = column.strip()
    if column == "#":
        return "rank"

    key = column.lower().replace("%", " pct ")
    key = re.sub(r"[^a-z0-9]+", "_", key)
    return key.strip("_")


def as_keys(columns):
    """Every column's key, guaranteed usable and all different.

    Two guards, because a JSON object cannot hold what a spreadsheet can:
    a heading of pure punctuation would give an empty key, and two headings
    that reduce to the same word would silently overwrite one another and lose
    a column.
    """
    keys, seen = [], {}
    for index, column in enumerate(columns, start=1):
        key = as_key(column) or f"column_{index}"

        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key = f"{key}_{seen[key]}"

        keys.append(key)
    return keys


def as_value(value):
    """One cell, in a form JSON can carry.

    Money and quantities arrive as Decimal and dates as date objects; both
    would otherwise fail to serialise. Decimals go out as strings so the two
    decimal places the reports round to survive the trip — a float would turn
    1234.50 into 1234.5, and some of these numbers are invoiced against.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float, bool, str)):
        return value
    return str(value)


def rows_as_json(columns, rows):
    """(columns, rows) -> a list of objects, one per row.

    The reports hand back a header row and a list of value rows — the same
    pair the CSV writer takes. Zipping them here is all the API has to do.
    """
    keys = as_keys(columns)
    return [
        {key: as_value(value) for key, value in zip(keys, row)}
        for row in rows
    ]
