from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import About

# Create your views here.
def about(request):
    return render(request, "about/about.html", {
        "about": About.objects.filter(is_active=True).first(),
    })


# what the editor is allowed to upload
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@staff_member_required          # only admin users, never the public
@require_POST
def upload_image(request):
    """Receives an image from the About editor and answers with its URL."""
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": "No file was sent."}, status=400)

    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        return JsonResponse({"error": f"{upload.content_type} is not an image."}, status=400)

    if upload.size > MAX_UPLOAD_BYTES:
        return JsonResponse({"error": "Images must be 5 MB or smaller."}, status=400)

    # storage adds a suffix if the name is taken, so nothing is overwritten
    path = default_storage.save(f"about/uploads/{upload.name}", upload)
    return JsonResponse({"location": default_storage.url(path)})
