from django.urls import path

from . import views


urlpatterns = [
    path('<uuid:property_id>/', views.property, name='property'),
    path('<uuid:property_id>/delete/', views.property_delete, name='property_delete'),
    path('<uuid:property_id>/is-public/', views.adjust_is_public_property, name='adjust_is_public_property'),
    path('', views.properties, name='properties'),
]
