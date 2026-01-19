"""URL configuration for hardware web interface."""

from django.urls import path

from . import views

app_name = "hardware"

urlpatterns = [
    path("devices/", views.DeviceSettingsView.as_view(), name="device-settings"),
]
