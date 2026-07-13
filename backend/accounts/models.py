from django.contrib.auth.models import AbstractUser
from django.db import models


class Tenant(models.Model):
    class Plan(models.TextChoices):
        FREE = 'free', 'Free'
        PRO = 'pro', 'Pro'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    name = models.CharField(max_length=255)
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.FREE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        OM = 'om', 'OM'
        BOD = 'bod', 'BOD'
        AM = 'am', 'AM'
        KCS = 'kcs', 'KCS'
        BQL = 'bql', 'BQL'
        TRAINER = 'trainer', 'Trainer'

    class JobTitle(models.TextChoices):
        QLNH = 'qlnh', 'Quản lý nhà hàng'
        GIAM_SAT = 'giam_sat', 'Giám sát'
        BEP_TRUONG = 'bep_truong', 'Bếp trưởng'
        BEP_PHO = 'bep_pho', 'Bếp phó'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        LOCKED = 'locked', 'Locked'

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name='users', null=True, blank=True
    )
    # Pham vi nha hang cho BQL/Trainer/KCS (port AuthService.gs::getScope). Admin/OM/BOD/AM
    # khong dung truong nay - vai tro cua ho la "toan he thong" (xem employees/permissions.py).
    restaurant = models.ForeignKey(
        'restaurants.Restaurant', on_delete=models.SET_NULL, related_name='staff_users',
        null=True, blank=True,
    )
    full_name = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TRAINER)
    job_title = models.CharField(max_length=20, choices=JobTitle.choices, blank=True, null=True)
    trainer_zone = models.CharField(max_length=100, blank=True, null=True)
    google_email = models.EmailField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    def __str__(self):
        return f"{self.username} ({self.tenant_id})"
