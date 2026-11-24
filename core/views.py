from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .decorators import roles
from .models import User, HallOwner, Booking, BookingPaymentProof, PaymentMethod, Commission, Withdrawal, AuditLog
from .services import mark_booking_paid

def login_view(request):
    if request.user.is_authenticated: return redirect("dashboard")
    if request.method == "POST":
        user = authenticate(request, username=request.POST.get("username",""), password=request.POST.get("password",""))
        if user is not None and user.is_active:
            login(request, user); return redirect("dashboard")
        messages.error(request, "Invalid credentials or inactive account.")
    return render(request, "core/login.html")

@login_required
def logout_view(request):
    if request.method == "POST": logout(request)
    return redirect("login")

def scope_owners(user):
    if user.is_superuser or user.role == User.Role.ADMIN: return HallOwner.objects.all()
    if user.role == User.Role.SUPER_AGENT:
        agent_ids = User.objects.filter(created_by=user, role=User.Role.AGENT).values_list("id", flat=True)
        return HallOwner.objects.filter(super_agent=user) | HallOwner.objects.filter(agent_id__in=agent_ids)
    return HallOwner.objects.filter(agent=user)

@login_required
def dashboard(request):
    user = request.user
    if user.is_superuser or user.role == User.Role.ADMIN:
        owners = HallOwner.objects.all()
        bookings_qs = Booking.objects.all()
        withdrawals_qs = Withdrawal.objects.all()
    else:
        owners = scope_owners(user).distinct()
        bookings_qs = Booking.objects.filter(hall_owner__in=owners)
        withdrawals_qs = Withdrawal.objects.filter(requester=user)
    commission_total = Commission.objects.filter(beneficiary=user).aggregate(v=Sum("amount"))["v"] or Decimal("0")
    withdrawn = Withdrawal.objects.filter(requester=user, status=Withdrawal.Status.APPROVED).aggregate(v=Sum("amount"))["v"] or Decimal("0")
    pending = Withdrawal.objects.filter(requester=user, status=Withdrawal.Status.PENDING).aggregate(v=Sum("amount"))["v"] or Decimal("0")
    context = {
        "owners_count": owners.count(), "bookings_count": bookings_qs.count(),
        "commission_total": commission_total, "withdrawn": withdrawn,
        "balance": commission_total - withdrawn - pending,
        "recent_bookings": bookings_qs.order_by("-created_at")[:6],
        "pending_owners": HallOwner.objects.filter(status="pending").count() if user.is_superuser or user.role == "admin" else 0,
        "pending_withdrawals": Withdrawal.objects.filter(status="pending").count() if user.is_superuser or user.role == "admin" else 0,
    }
    return render(request, "core/dashboard.html", context)

@login_required
def hall_owners(request):
    user = request.user
    qs = scope_owners(user).select_related("agent","super_agent").order_by("-created_at").distinct()
    if request.method == "POST":
        if user.role not in [User.Role.AGENT, User.Role.SUPER_AGENT] and not user.is_superuser: raise PermissionDenied
        name, email = request.POST.get("name","").strip(), request.POST.get("email","").strip()
        photo = request.FILES.get("contract_photo")
        if not name or not email or not photo:
            messages.error(request, "Name, email and contract photo are required.")
        else:
            agent = user if user.role == User.Role.AGENT else None
            super_agent = (user if user.role == User.Role.SUPER_AGENT else user.created_by if user.role == User.Role.AGENT else None)
            HallOwner.objects.create(name=name, email=email, phone=request.POST.get("phone",""), contract_photo=photo,
                agent=agent, super_agent=super_agent, notes=request.POST.get("notes",""))
            messages.success(request, "Hall owner submitted for admin approval.")
        return redirect("hall_owners")
    return render(request, "core/hall_owners.html", {"owners": qs})

@roles("admin")
def owner_status(request, pk, status):
    if status not in ["approved","rejected"]: raise PermissionDenied
    owner = get_object_or_404(HallOwner, pk=pk)
    owner.status = status
    owner.approved_at = timezone.now() if status == "approved" else None
    owner.save()
    AuditLog.objects.create(actor=request.user, action=f"hall_owner_{status}", detail=owner.name)
    messages.success(request, f"Hall owner {status}.")
    return redirect("hall_owners")

@roles("admin","super_agent")
def agents(request):
    if request.user.role == "super_agent":
        qs = User.objects.filter(created_by=request.user, role=User.Role.AGENT)
    else:
        qs = User.objects.filter(role__in=[User.Role.AGENT,User.Role.SUPER_AGENT])
    if request.method == "POST":
        if request.user.role != "super_agent": raise PermissionDenied
        username = request.POST.get("username","").strip()
        password = request.POST.get("password","")
        if not username or len(password) < 8:
            messages.error(request, "Enter a username and password of at least 8 characters.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "That username already exists.")
        else:
            User.objects.create_user(username=username, password=password, role=User.Role.AGENT, created_by=request.user,
                first_name=request.POST.get("first_name",""), last_name=request.POST.get("last_name",""), email=request.POST.get("email",""))
            messages.success(request, "Agent account created.")
        return redirect("agents")
    return render(request, "core/agents.html", {"agents": qs.order_by("-date_joined")})

@roles("super_agent")
def suspend_agent(request, pk):
    agent = get_object_or_404(User, pk=pk, created_by=request.user, role=User.Role.AGENT)
    if request.method == "POST":
        reason = request.POST.get("reason","").strip()
        if not reason: messages.error(request, "A suspension reason is required.")
        else:
            agent.is_active = False; agent.suspension_reason = reason; agent.save()
            AuditLog.objects.create(actor=request.user, action="agent_suspended", detail=f"{agent.username}: {reason}")
            messages.success(request, "Agent access suspended.")
    return redirect("agents")

@roles("admin")
def activate_agent(request, pk):
    user = get_object_or_404(User, pk=pk, role__in=["agent","super_agent"])
    user.is_active = True; user.suspension_reason = ""; user.save()
    AuditLog.objects.create(actor=request.user, action="user_activated", detail=user.username)
    return redirect("agents")

@roles("admin")
def promote_agent(request, pk):
    user = get_object_or_404(User, pk=pk, role="agent")
    user.role = "super_agent"; user.created_by = None; user.save()
    AuditLog.objects.create(actor=request.user, action="agent_promoted", detail=user.username)
    messages.success(request, "Agent promoted to super agent; previous reporting link removed.")
    return redirect("agents")

@roles("admin")
def bookings(request):
    qs = Booking.objects.select_related("hall_owner","agent","super_agent").prefetch_related("payment_proofs").order_by("-created_at")
    if request.method == "POST":
        owner = get_object_or_404(HallOwner, pk=request.POST.get("hall_owner"), status="approved")
        try:
            total = Decimal(request.POST.get("total_amount","0"))
            advance = Decimal(request.POST.get("advance_amount","0"))
            if total <= 0 or advance < 0 or advance > total: raise ValueError
        except Exception:
            messages.error(request, "Enter valid total and advance amounts."); return redirect("bookings")
        booking = Booking.objects.create(hall_owner=owner, agent=owner.agent, super_agent=owner.super_agent,
            event_name=request.POST.get("event_name",""), event_date=request.POST.get("event_date") or None,
            total_amount=total, advance_amount=advance, other_costs=request.POST.get("other_costs",""),
            created_by=request.user, status="partial")
        images = request.FILES.getlist("payment_proofs")
        if len(images) > 20:
            booking.delete(); messages.error(request, "A maximum of 20 payment proofs is allowed."); return redirect("bookings")
        for image in images: BookingPaymentProof.objects.create(booking=booking, image=image)
        messages.success(request, "Booking recorded.")
        return redirect("bookings")
    return render(request, "core/bookings.html", {"bookings": qs, "approved_owners": HallOwner.objects.filter(status="approved")})

@roles("admin")
def add_booking_proofs(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if request.method == "POST":
        images = request.FILES.getlist("payment_proofs")
        try:
            amount = Decimal(request.POST.get("amount", "0"))
            if amount < 0: raise ValueError
        except Exception:
            messages.error(request, "Enter a valid payment amount.")
            return redirect("bookings")
        if not images:
            messages.error(request, "Choose at least one payment proof image.")
        elif booking.payment_proofs.count() + len(images) > 20:
            messages.error(request, "A maximum of 20 proof images is allowed per booking.")
        else:
            # The entered payment amount is attached to the first proof; additional
            # images document the same transfer batch without double-counting it.
            for index, image in enumerate(images):
                BookingPaymentProof.objects.create(
                    booking=booking, image=image, amount=amount if index == 0 else Decimal("0"),
                    note=request.POST.get("note", "")
                )
            messages.success(request, "Payment proof added.")
    return redirect("bookings")

@roles("admin")
def booking_paid(request, pk):
    if request.method == "POST":
        booking = get_object_or_404(Booking, pk=pk)
        received = booking.advance_amount + (booking.payment_proofs.aggregate(v=Sum("amount"))["v"] or Decimal("0"))
        if received < booking.total_amount:
            messages.error(request, f"Cannot mark paid: recorded payments are {received:.2f}; total is {booking.total_amount:.2f}. Add the remaining payment and proof.")
            return redirect("bookings")
        mark_booking_paid(booking, request.user)
        messages.success(request, "Booking marked paid; commission entries have been posted.")
    return redirect("bookings")

@login_required
def payment_methods(request):
    if request.method == "POST":
        if all(request.POST.get(k,"").strip() for k in ["operator","holder_name","phone"]):
            PaymentMethod.objects.create(owner=request.user, operator=request.POST["operator"], holder_name=request.POST["holder_name"], phone=request.POST["phone"])
            messages.success(request, "Payment method saved.")
        else: messages.error(request, "Complete all payment method fields.")
        return redirect("payment_methods")
    return render(request, "core/payment_methods.html", {"methods": request.user.payment_methods.all()})

@login_required
def payment_method_delete(request, pk):
    method = get_object_or_404(PaymentMethod, pk=pk, owner=request.user)
    if request.method == "POST": method.delete(); messages.success(request, "Payment method deleted.")
    return redirect("payment_methods")

@login_required
def withdrawals(request):
    if request.method == "POST":
        method = get_object_or_404(PaymentMethod, pk=request.POST.get("payment_method"), owner=request.user)
        try: amount = Decimal(request.POST.get("amount","0"))
        except Exception: amount = Decimal("0")
        earned = Commission.objects.filter(beneficiary=request.user).aggregate(v=Sum("amount"))["v"] or Decimal("0")
        paid = Withdrawal.objects.filter(requester=request.user, status=Withdrawal.Status.APPROVED).aggregate(v=Sum("amount"))["v"] or Decimal("0")
        pending = Withdrawal.objects.filter(requester=request.user, status=Withdrawal.Status.PENDING).aggregate(v=Sum("amount"))["v"] or Decimal("0")
        if amount <= 0 or amount > earned - paid - pending:
            messages.error(request, "Requested amount exceeds your available balance.")
        else:
            Withdrawal.objects.create(requester=request.user, payment_method=method, amount=amount)
            messages.success(request, "Withdrawal request submitted.")
        return redirect("withdrawals")
    qs = Withdrawal.objects.filter(requester=request.user) if request.user.role != "admin" and not request.user.is_superuser else Withdrawal.objects.select_related("requester","payment_method")
    return render(request, "core/withdrawals.html", {"withdrawals": qs.order_by("-requested_at"), "methods": request.user.payment_methods.all()})

@roles("admin")
def withdrawal_review(request, pk):
    withdrawal = get_object_or_404(Withdrawal, pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "approve" and request.FILES.get("proof"):
            withdrawal.status = "approved"; withdrawal.proof = request.FILES["proof"]
        elif action == "reject": withdrawal.status = "rejected"
        else:
            messages.error(request, "Approval requires payment proof."); return redirect("withdrawals")
        withdrawal.admin_note = request.POST.get("admin_note","")
        withdrawal.reviewed_by = request.user; withdrawal.reviewed_at = timezone.now(); withdrawal.save()
        AuditLog.objects.create(actor=request.user, action=f"withdrawal_{withdrawal.status}", detail=f"#{withdrawal.pk}")
        messages.success(request, f"Withdrawal {withdrawal.status}.")
    return redirect("withdrawals")

@login_required
def history(request):
    if request.user.is_superuser or request.user.role == "admin":
        commissions = Commission.objects.select_related("booking","beneficiary","booking__hall_owner")
    else:
        commissions = Commission.objects.filter(beneficiary=request.user).select_related("booking","booking__hall_owner")
    return render(request, "core/history.html", {"commissions": commissions, "logs": AuditLog.objects.all()[:100] if request.user.role == "admin" or request.user.is_superuser else []})
