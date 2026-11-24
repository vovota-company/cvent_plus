from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
class ActiveAccountMiddleware:
    """Force disabled business accounts out while leaving login/admin endpoints reachable."""
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            if not request.user.is_active:
                logout(request)
                return redirect(reverse("login"))
        return self.get_response(request)
