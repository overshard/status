from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from accounts import urls as accounts_urls
from pages import urls as pages_urls
from properties import urls as properties_urls


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include(accounts_urls)),
    path("properties/", include(properties_urls)),
    path("", include(pages_urls)),
]


if settings.DEBUG:
    urlpatterns.append(path("403/", TemplateView.as_view(template_name="403.html")))
    urlpatterns.append(path("404/", TemplateView.as_view(template_name="404.html")))
    urlpatterns.append(path("500/", TemplateView.as_view(template_name="500.html")))
    urlpatterns += static("media/", document_root=settings.MEDIA_ROOT)
