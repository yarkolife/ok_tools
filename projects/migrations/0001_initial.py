# Generated by Django 4.1 on 2022-08-17 14:06

from django.db import migrations
from django.db import models
import django.db.models.deletion
import projects.models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="MediaEducationSupervisor",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=255, null=True, verbose_name="Full name"
                    ),
                ),
            ],
            options={
                "verbose_name": "Media education supervisor",
                "verbose_name_plural": "Media education supervisors",
            },
        ),
        migrations.CreateModel(
            name="ProjectCategory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=255, null=True, verbose_name="Project category"
                    ),
                ),
            ],
            options={
                "verbose_name": "Project category",
                "verbose_name_plural": "Project categories",
            },
        ),
        migrations.CreateModel(
            name="ProjectLeader",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=255, null=True, verbose_name="Full name"
                    ),
                ),
            ],
            options={
                "verbose_name": "Project leader",
                "verbose_name_plural": "Project leaders",
            },
        ),
        migrations.CreateModel(
            name="TargetGroup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=255, null=True, verbose_name="Target group"
                    ),
                ),
            ],
            options={
                "verbose_name": "Target group",
                "verbose_name_plural": "Target groups",
            },
        ),
        migrations.CreateModel(
            name="Project",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        max_length=255, verbose_name="Project title"),
                ),
                (
                    "topic",
                    models.CharField(
                        blank=True, max_length=255, null=True, verbose_name="Topic"
                    ),
                ),
                ("duration", models.DurationField(verbose_name="Duration")),
                (
                    "begin_date",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Start date"
                    ),
                ),
                (
                    "end_date",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="End date"
                    ),
                ),
                ("external_venue", models.BooleanField(
                    verbose_name="External venue")),
                (
                    "jugendmedienschutz",
                    models.BooleanField(verbose_name="Jugendmedienschutz"),
                ),
                (
                    "media_education_supervisor",
                    models.ForeignKey(
                        default=projects.models.default_category,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="projects.mediaeducationsupervisor",
                    ),
                ),
                (
                    "project_category",
                    models.ForeignKey(
                        default=projects.models.default_category,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="projects.projectcategory",
                    ),
                ),
                (
                    "project_leader",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="projects.projectleader",
                    ),
                ),
                (
                    "target_group",
                    models.ForeignKey(
                        default=projects.models.default_target_group,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="projects.targetgroup",
                    ),
                ),
            ],
            options={
                "verbose_name": "Project",
                "verbose_name_plural": "Projects",
            },
        ),
    ]
