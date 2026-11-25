
from django.db import models
from django.contrib.auth.models import User
from resources.models import Resource


class Booking(models.Model):

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('ISSUED', 'Issued'),
        ('RETURNED', 'Returned'),
        ('CANCELLED', 'Cancelled'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    resource = models.ForeignKey(
        Resource,
        on_delete=models.PROTECT,
        related_name='bookings'
    )

    quantity = models.PositiveIntegerField(default=1)

    returned_quantity = models.PositiveIntegerField(default=0)

    damaged_quantity = models.PositiveIntegerField(default=0)

    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    purpose = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_bookings'
    )

    issued_at = models.DateTimeField(null=True, blank=True)

    returned_at = models.DateTimeField(null=True, blank=True)

    return_condition = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.resource.name} ({self.quantity} units)"
        )
