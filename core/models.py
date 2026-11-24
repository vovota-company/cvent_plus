from decimal import Decimal
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        SUPER_AGENT = "super_agent", "Super agent"
        AGENT = "agent", "Agent"
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.AGENT)
    created_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_users")
    suspension_reason = models.TextField(blank=True)
    def __str__(self): return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

class HallOwner(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
    name = models.CharField(max_length=180)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    contract_photo = models.ImageField(upload_to="contracts/")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="hall_owners")
    super_agent = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="direct_hall_owners")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    def __str__(self): return self.name

class PaymentMethod(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_methods")
    operator = models.CharField(max_length=80)
    holder_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.operator} • {self.phone}"

class Booking(models.Model):
    class Status(models.TextChoices):
        PARTIAL = "partial", "Partially paid"
        PAID = "paid", "Paid / approved"
        CANCELLED = "cancelled", "Cancelled"
    hall_owner = models.ForeignKey(HallOwner, on_delete=models.PROTECT, related_name="bookings")
    super_agent = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="super_agent_bookings")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="agent_bookings")
    event_name = models.CharField(max_length=180, blank=True)
    event_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    advance_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    other_costs = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PARTIAL)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_bookings")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    @property
    def remaining_amount(self): return max(Decimal("0"), self.total_amount - self.advance_amount)
    def __str__(self): return f"Booking #{self.pk} — {self.hall_owner.name}"

class BookingPaymentProof(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="payment_proofs")
    image = models.ImageField(upload_to="booking-proofs/")
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    note = models.CharField(max_length=240, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

class Commission(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="commissions")
    beneficiary = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="commissions")
    rate = models.DecimalField(max_digits=5, decimal_places=4)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["booking", "beneficiary"], name="unique_booking_beneficiary_commission")]
        ordering = ["-created_at"]

class Withdrawal(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="withdrawals")
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    proof = models.ImageField(upload_to="withdrawal-proofs/", null=True, blank=True)
    admin_note = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_withdrawals")

class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=120)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-created_at"]
