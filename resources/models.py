
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Location(models.Model):
    name = models.CharField(max_length=100)
    building = models.CharField(max_length=100)
    floor = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} - {self.building}"


class Resource(models.Model):

    TRACKING_CHOICES = [
        ('INDIVIDUAL', 'Individual Asset'),
        ('QUANTITY', 'Quantity Based'),
    ]

    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('UNAVAILABLE', 'Unavailable'),
        ('MAINTENANCE', 'Under Maintenance'),
    ]

    CONDITION_CHOICES = [
        ('EXCELLENT', 'Excellent'),
        ('GOOD', 'Good'),
        ('FAIR', 'Fair'),
        ('DAMAGED', 'Damaged'),
    ]

    name = models.CharField(max_length=150)

    tracking_type = models.CharField(
        max_length=20,
        choices=TRACKING_CHOICES,
        default='INDIVIDUAL'
    )

    asset_tag = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True
    )

    total_quantity = models.PositiveIntegerField(default=1)

    damaged_quantity = models.PositiveIntegerField(default=0)

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='resources'
    )

    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='resources'
    )

    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='AVAILABLE'
    )

    condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        default='GOOD'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.tracking_type == 'INDIVIDUAL':
            return f"{self.name} ({self.asset_tag})"

        return f"{self.name} ({self.total_quantity} units)"
