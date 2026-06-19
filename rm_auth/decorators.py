from functools import wraps

from django.conf import settings
from django.shortcuts import redirect

from .utils import get_authenticated_rm


def rm_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not get_authenticated_rm(request):
            return redirect(settings.LOGIN_URL)
        return view_func(request, *args, **kwargs)

    return wrapper
