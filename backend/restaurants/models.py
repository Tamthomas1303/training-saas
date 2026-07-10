from django.db import models

from accounts.models import Tenant


class Restaurant(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='restaurants')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        unique_together = ('tenant', 'code')

    def __str__(self):
        return f'{self.code} - {self.name}'
