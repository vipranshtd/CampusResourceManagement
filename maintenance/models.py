
from django.db import models
from django.contrib.auth.models import User
from resources.models import Resource

class MaintenanceRecord(models.Model):
    STATUS_CHOICES = [
        ('REPORTED', 'Reported'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
    ]

    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, related_name='maintenance_records')
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reported_maintenance')
    issue_description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='REPORTED')
    reported_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.resource.name} - {self.status}"