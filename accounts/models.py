
from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    ROLE_CHOICES = [
        ('STUDENT', 'Student'),
        ('FACULTY', 'Faculty'),
        ('STAFF', 'Resource Staff'),
        ('ADMIN', 'Administrator'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='STUDENT')
    phone = models.CharField(max_length=15, blank=True)
    department = models.CharField(max_length=100, blank=True)
    institutional_id = models.CharField(max_length=30,unique=True,null=True,blank=True)
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
