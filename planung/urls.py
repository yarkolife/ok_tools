from . import views
from django.urls import path


urlpatterns = [
    path(
        "license/<int:number>/",
        views.get_license_by_number,
        name="get_license_by_number",
    ),
    path("day-plan/", views.save_day_plan, name="save_day_plan"),  # POST method
    path("day-plan/<slug:iso_date>/", views.day_plan_detail, name="day_plan_detail"),
]
