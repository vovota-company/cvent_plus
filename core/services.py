from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from .models import Commission, AuditLog, Booking

@transaction.atomic
def mark_booking_paid(booking, actor):
    booking = Booking.objects.select_for_update().get(pk=booking.pk)
    if booking.status == Booking.Status.PAID:
        return booking
    booking.status = Booking.Status.PAID
    booking.paid_at = timezone.now()
    booking.save(update_fields=["status", "paid_at"])
    base = booking.total_amount
    # A direct owner belongs to the super agent. An owner introduced by an agent
    # pays 1% to that agent and 1% to the associated super agent.
    if booking.agent_id:
        beneficiaries = [(booking.agent, Decimal("0.01"))]
        if booking.super_agent_id:
            beneficiaries.append((booking.super_agent, Decimal("0.01")))
    elif booking.super_agent_id:
        beneficiaries = [(booking.super_agent, Decimal("0.02"))]
    else:
        beneficiaries = []
    for user, rate in beneficiaries:
        amount = (base * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        Commission.objects.get_or_create(
            booking=booking, beneficiary=user,
            defaults={"rate": rate, "amount": amount},
        )
    AuditLog.objects.create(actor=actor, action="booking_marked_paid", detail=f"Booking #{booking.pk}")
    return booking
