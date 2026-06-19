from django.contrib.auth.hashers import check_password, make_password
from django.conf import settings
from django.db import models


class RMUser(models.Model):
    user_id = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=128)
    email = models.EmailField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_rms",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Relationship Manager"
        verbose_name_plural = "Relationship Managers"
        ordering = ["user_id"]

    def __str__(self):
        return self.user_id

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)
