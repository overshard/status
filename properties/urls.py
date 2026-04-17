from django.urls import path

from . import views


urlpatterns = [
    path('<uuid:property_id>/', views.property, name='property'),
    path('<uuid:property_id>/delete/', views.property_delete, name='property_delete'),
    path('<uuid:property_id>/is-public/', views.adjust_is_public_property, name='adjust_is_public_property'),
    path('<uuid:property_id>/status/', views.property_status, name='property_status'),
    path('<uuid:property_id>/recrawl/', views.property_recrawl, name='property_recrawl'),
    path('<uuid:property_id>/rerun-lighthouse/', views.property_rerun_lighthouse, name='property_rerun_lighthouse'),
    path('', views.properties, name='properties'),
]
