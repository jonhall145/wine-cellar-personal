"""URL configuration for hardware web interface."""

from django.urls import path

from . import views

app_name = "hardware"

urlpatterns = [
    path("reviews/", views.PositionReviewView.as_view(), name="position-reviews"),
    path("devices/", views.DeviceSettingsView.as_view(), name="device-settings"),
    path("rack-config/", views.RackConfigView.as_view(), name="rack-config"),
]
