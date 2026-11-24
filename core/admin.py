from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, HallOwner, PaymentMethod, Booking, BookingPaymentProof, Commission, Withdrawal, AuditLog
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Cvent Plus access", {"fields": ("role", "created_by", "suspension_reason")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Cvent Plus access", {"fields": ("role", "created_by")}),)
for model in [HallOwner, PaymentMethod, Booking, BookingPaymentProof, Commission, Withdrawal, AuditLog]:
    admin.site.register(model)
