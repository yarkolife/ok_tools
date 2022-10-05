# Generated by Django 4.0.5 on 2022-10-05 08:45

from django.db import migrations
from django.db import models
import django.db.models.deletion
import projects.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='MediaEducationSupervisor',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Full name')),
            ],
            options={
                'verbose_name': 'Media education supervisor',
                'verbose_name_plural': 'Media education supervisors',
            },
        ),
        migrations.CreateModel(
            name='ProjectCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255,
                 verbose_name='Project category')),
            ],
            options={
                'verbose_name': 'Project category',
                'verbose_name_plural': 'Project categories',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='ProjectLeader',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Full name')),
            ],
            options={
                'verbose_name': 'Project leader',
                'verbose_name_plural': 'Project leaders',
            },
        ),
        migrations.CreateModel(
            name='TargetGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Target group')),
            ],
            options={
                'verbose_name': 'Target group',
                'verbose_name_plural': 'Target groups',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(
                    max_length=255, verbose_name='Project title')),
                ('topic', models.CharField(blank=True,
                 max_length=255, null=True, verbose_name='Topic')),
                ('duration', models.DurationField(
                    blank=True, help_text='Total amount of time spend.', null=True, verbose_name='Duration')),
                ('begin_date', models.DateTimeField(verbose_name='Start date')),
                ('end_date', models.DateTimeField(verbose_name='End date')),
                ('external_venue', models.BooleanField(
                    verbose_name='External venue')),
                ('jugendmedienschutz', models.BooleanField(
                    verbose_name='Jugendmedienschutz')),
                ('democracy_project', models.BooleanField(
                    default=False, verbose_name='Democracy project')),
                ('tn_0_bis_6', models.IntegerField(
                    default=0, verbose_name='bis 6 Jahre')),
                ('tn_7_bis_10', models.IntegerField(
                    default=0, verbose_name='7-10 Jahre')),
                ('tn_11_bis_14', models.IntegerField(
                    default=0, verbose_name='11-14 Jahre')),
                ('tn_15_bis_18', models.IntegerField(
                    default=0, verbose_name='15-18 Jahre')),
                ('tn_19_bis_34', models.IntegerField(
                    default=0, verbose_name='19-34 Jahre')),
                ('tn_35_bis_50', models.IntegerField(
                    default=0, verbose_name='35-50 Jahre')),
                ('tn_51_bis_65', models.IntegerField(
                    default=0, verbose_name='51-65 Jahre')),
                ('tn_ueber_65', models.IntegerField(
                    default=0, verbose_name='über 65 Jahre')),
                ('tn_age_not_given', models.IntegerField(
                    default=0, verbose_name='ohne Angabe')),
                ('tn_female', models.IntegerField(
                    default=0, verbose_name='weiblich')),
                ('tn_male', models.IntegerField(default=0, verbose_name='männlich')),
                ('tn_gender_not_given', models.IntegerField(
                    default=0, verbose_name='ohne Angabe')),
                ('tn_diverse', models.IntegerField(
                    default=0, verbose_name='diverse')),
                ('media_education_supervisors', models.ManyToManyField(
                    to='projects.mediaeducationsupervisor')),
                ('project_category', models.ForeignKey(default=projects.models.default_category,
                 on_delete=django.db.models.deletion.CASCADE, to='projects.projectcategory')),
                ('project_leader', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, to='projects.projectleader')),
                ('target_group', models.ForeignKey(default=projects.models.default_target_group,
                 on_delete=django.db.models.deletion.CASCADE, to='projects.targetgroup')),
            ],
            options={
                'verbose_name': 'Project',
                'verbose_name_plural': 'Projects',
            },
        ),
    ]
