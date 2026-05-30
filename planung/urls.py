from . import views
from django.urls import path


urlpatterns = [
    path(
        "license/<int:number>/",
        views.get_license_by_number,
        name="get_license_by_number",
    ),
    path("day-plan/", views.save_day_plan, name="save_day_plan"),
    path("day-plan/<str:iso_date>/", views.day_plan_detail, name="day_plan_detail"),
    path("day-plan/<str:iso_date>/export/", views.export_day_plan, name="export_day_plan"),
    path("planning/week-stats/", views.week_stats, name="planning_week_stats"),
    path("planning/templates/", views.list_templates, name="planning_templates"),
    path("planning/templates/apply/", views.apply_template, name="planning_template_apply"),
    path("planning/copy/", views.copy_plan, name="planning_copy_plan"),
    path("planning/playout/config/", views.playout_config, name="planning_playout_config"),
    path("planning/playout/missing/", views.playout_missing_media, name="playout_playout_missing"),
    path("planning/playout/metadata/", views.send_playout_metadata, name="planning_playout_metadata"),
    path("planning/playout/schedule/", views.send_playout_schedule, name="planning_playout_schedule"),
]
