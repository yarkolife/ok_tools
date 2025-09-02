from django.db import models
from django.utils.translation import gettext_lazy as _


class DashboardCache(models.Model):
    """Base model for caching dashboard aggregated data."""
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cache_key = models.CharField(max_length=255, unique=True)
    data = models.JSONField()
    expires_at = models.DateTimeField()
    
    class Meta:
        verbose_name = _('Dashboard Cache')
        verbose_name_plural = _('Dashboard Caches')
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.cache_key} (expires: {self.expires_at})"


class UserStatistics(models.Model):
    """Cached user statistics for dashboard."""
    
    date = models.DateField()
    total_users = models.IntegerField(default=0)
    male_users = models.IntegerField(default=0)
    female_users = models.IntegerField(default=0)
    diverse_users = models.IntegerField(default=0)
    verified_users = models.IntegerField(default=0)
    member_users = models.IntegerField(default=0)
    new_users = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = _('User Statistics')
        verbose_name_plural = _('User Statistics')
        unique_together = ['date']
        ordering = ['-date']
    
    def __str__(self):
        return f"User stats for {self.date}"


class LicenseStatistics(models.Model):
    """Cached license statistics for dashboard."""
    
    date = models.DateField()
    total_licenses = models.IntegerField(default=0)
    confirmed_licenses = models.IntegerField(default=0)
    new_licenses = models.IntegerField(default=0)
    licenses_by_category = models.JSONField(default=dict)
    licenses_by_media_authority = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = _('License Statistics')
        verbose_name_plural = _('License Statistics')
        unique_together = ['date']
        ordering = ['-date']
    
    def __str__(self):
        return f"License stats for {self.date}"


class ContributionStatistics(models.Model):
    """Cached contribution statistics for dashboard."""
    
    date = models.DateField()
    total_contributions = models.IntegerField(default=0)
    primary_contributions = models.IntegerField(default=0)
    live_contributions = models.IntegerField(default=0)
    contributions_by_media_authority = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = _('Contribution Statistics')
        verbose_name_plural = _('Contribution Statistics')
        unique_together = ['date']
        ordering = ['-date']
    
    def __str__(self):
        return f"Contribution stats for {self.date}"
