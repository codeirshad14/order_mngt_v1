"""URLs for settings_prodtest only: the real urls.py plus /media/, which
nginx serves on the server but nothing does here once DEBUG is off."""

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.urls import re_path
from django.views.static import serve

from .urls import urlpatterns as real_urlpatterns

urlpatterns = [
    re_path(r"^media/(?P<path>.*)$", login_not_required(serve), {"document_root": settings.MEDIA_ROOT}),
    *real_urlpatterns,
]
