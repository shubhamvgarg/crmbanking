from django.contrib import admin

from .forms import RMUserAdminForm
from .models import RMUser


@admin.register(RMUser)
class RMUserAdmin(admin.ModelAdmin):
    form = RMUserAdminForm
    list_display = ("user_id", "email", "is_active", "created_by", "created_at")
    list_filter = ("is_active",)
    search_fields = ("user_id", "email")
    readonly_fields = ("created_by", "created_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
