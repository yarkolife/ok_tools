from django.contrib import admin
from .models import DashboardCache, UserStatistics, LicenseStatistics, ContributionStatistics


@admin.register(DashboardCache)
class DashboardCacheAdmin(admin.ModelAdmin):
    list_display = ['cache_key', 'created_at', 'updated_at', 'expires_at']
    list_filter = ['created_at', 'updated_at', 'expires_at']
    search_fields = ['cache_key']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UserStatistics)
class UserStatisticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_users', 'male_users', 'female_users', 'verified_users', 'member_users', 'new_users']
    list_filter = ['date']
    ordering = ['-date']


@admin.register(LicenseStatistics)
class LicenseStatisticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_licenses', 'confirmed_licenses', 'new_licenses']
    list_filter = ['date']
    ordering = ['-date']


@admin.register(ContributionStatistics)
class ContributionStatisticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_contributions', 'primary_contributions', 'live_contributions']
    list_filter = ['date']
    ordering = ['-date']
