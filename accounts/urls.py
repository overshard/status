from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(extra_context={"title": "Login"}),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(extra_context={"title": "Logout"}),
        name="logout",
    ),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            extra_context={"title": "Password change"}
        ),
        name="password_change",
    ),
    path(
        "password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            extra_context={"title": "Password change done"}
        ),
        name="password_change_done",
    ),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(extra_context={"title": "Password reset"}),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            extra_context={"title": "Password reset done"}
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            extra_context={"title": "Password reset confirm"}
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            extra_context={"title": "Password reset complete"}
        ),
        name="password_reset_complete",
    ),
    path("profile/", views.profile, name="profile"),
]
