from django.shortcuts import get_object_or_404, render

from products.models import Product

from .models import Catelog, NewArrival

# Create your views here.


def catelog(request):
    """All catelogs, each one a named group of products."""
    catelogs = Catelog.objects.prefetch_related("products")
    return render(request, "catelog/catelog.html", {"catelogs": catelogs})


def detail(request, pk):
    """One catelog with every product inside it."""
    catelog = get_object_or_404(Catelog, pk=pk)
    # prefetch new_arrivals so the "New" badge costs no query per card
    products = catelog.products.select_related("brand", "unit").prefetch_related("new_arrivals")

    return render(request, "catelog/catelog_detail.html", {
        "catelog": catelog,
        "products": products,
    })


def new_arrival(request):
    """Products that appear in any new arrival list."""
    products = (
        Product.objects.select_related("brand", "unit")
        .prefetch_related("new_arrivals")
        .filter(new_arrivals__isnull=False)
        .distinct()
    )
    return render(request, "catelog/new_arrival.html", {
        "products": products,
        "lists": NewArrival.objects.all(),
    })
