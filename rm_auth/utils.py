from django.conf import settings

from .models import RMUser


def get_authenticated_rm(request):
    rm_id = request.session.get(settings.RM_SESSION_KEY)
    if not rm_id:
        return None
    try:
        return RMUser.objects.get(pk=rm_id, is_active=True)
    except RMUser.DoesNotExist:
        return None
