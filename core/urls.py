from django.urls import path
from . import views
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("hall-owners/", views.hall_owners, name="hall_owners"),
    path("hall-owners/<int:pk>/status/<str:status>/", views.owner_status, name="owner_status"),
    path("agents/", views.agents, name="agents"),
    path("agents/<int:pk>/suspend/", views.suspend_agent, name="suspend_agent"),
    path("agents/<int:pk>/activate/", views.activate_agent, name="activate_agent"),
    path("agents/<int:pk>/promote/", views.promote_agent, name="promote_agent"),
    path("bookings/", views.bookings, name="bookings"),
    path("bookings/<int:pk>/proofs/", views.add_booking_proofs, name="add_booking_proofs"),
    path("bookings/<int:pk>/paid/", views.booking_paid, name="booking_paid"),
    path("payment-methods/", views.payment_methods, name="payment_methods"),
    path("payment-methods/<int:pk>/delete/", views.payment_method_delete, name="payment_method_delete"),
    path("withdrawals/", views.withdrawals, name="withdrawals"),
    path("withdrawals/<int:pk>/review/", views.withdrawal_review, name="withdrawal_review"),
    path("history/", views.history, name="history"),
]
