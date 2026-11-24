from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
def roles(*allowed):
    def deco(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not (request.user.is_superuser or request.user.role in allowed):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapped
    return deco
