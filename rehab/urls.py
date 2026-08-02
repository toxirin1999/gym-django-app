from django.urls import path

from . import views

app_name = "rehab"

urlpatterns = [
    path("", views.placeholder, name="placeholder"),
]
