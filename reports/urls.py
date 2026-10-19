
from django.urls import path
from . import views

app_name = "reports"

# one route per card on the index; the slug here matches REPORT_CARDS so the
# card and the page it opens can never drift apart
urlpatterns = [

    path("reports", views.reports, name="reports"),

    path("order-book", views.order_book, name="order_book"),
    path("pending-payment", views.pending_payment, name="pending_payment"),
    path("top-orders", views.top_orders, name="top_orders"),
    path("due-count", views.due_count, name="due_count"),
    path("top-items", views.top_items, name="top_items"),
    path("order-wise-items", views.order_wise_items, name="order_wise_items"),
    path("item-movement", views.item_movement, name="item_movement"),
    path("item-summary", views.item_summary, name="item_summary"),
    path("order-gst", views.order_gst, name="order_gst"),

    # sales executive
    path("sales-performance", views.sales_performance, name="sales_performance"),
    path("sales-dealers", views.sales_dealers, name="sales_dealers"),
    path("sales-comparison", views.sales_comparison, name="sales_comparison"),
    path("sales-items", views.sales_items, name="sales_items"),
    path("sales-collection", views.sales_collection, name="sales_collection"),

    # attendance
    path("visit-report", views.visit_report, name="visit_report"),

    # csv | excel | pdf, for whichever report the slug names. The filters
    # ride along on the query string, so a download matches the screen.
    path("export/<slug:slug>/<str:fmt>", views.export, name="export"),

]
