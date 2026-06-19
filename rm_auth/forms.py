from django import forms

from .models import RMUser


class RMUserAdminForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Required when creating a new RM. Leave blank to keep the current password.",
    )

    class Meta:
        model = RMUser
        fields = ["user_id", "email", "is_active", "password"]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        if not self.instance.pk and not password:
            raise forms.ValidationError({"password": "Password is required when creating an RM account."})
        return cleaned_data

    def save(self, commit=True):
        rm_user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            rm_user.set_password(password)
        if commit:
            rm_user.save()
        return rm_user


class LoginForm(forms.Form):
    user_id = forms.CharField(
        max_length=50,
        label="User ID",
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class ChangePasswordForm(forms.Form):
    user_id = forms.CharField(max_length=50, label="User ID")
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        label="Current password",
    )
    email = forms.EmailField(label="Registered email")
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        label="New password",
        min_length=8,
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        label="Confirm new password",
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError("New passwords do not match.")
        return cleaned_data
