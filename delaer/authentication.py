from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiKey


class ApiKeyAuthentication(BaseAuthentication):
    """Reads the X-API-Key header and signs the request in as that key's user.

        curl -H "X-API-Key: <key>" http://127.0.0.1:8000/api/products/
    """

    def authenticate(self, request):
        key = request.headers.get("X-API-Key")
        if not key:
            return None          # no key sent — let other auth classes try

        try:
            api_key = ApiKey.objects.select_related("user").get(key=key, is_active=True)
        except ApiKey.DoesNotExist:
            raise AuthenticationFailed("Invalid or inactive API key.")

        api_key.touch()
        return (api_key.user, api_key)

    def authenticate_header(self, request):
        # makes DRF answer 401 rather than 403 when the key is missing
        return "X-API-Key"
