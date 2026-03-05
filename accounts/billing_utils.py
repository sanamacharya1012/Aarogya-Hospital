from django.utils import timezone
from decimal import Decimal

def calc_ipd_days(admitted_at, discharged_at=None):
    """
    Mininmum 1 day charge.
    """
    start = admitted_at.date()
    end = discharged_at.date() if discharged_at else timezone.localdate()
    days = (end-start).days + 1
    return max(days, 1)

def opd_appointment_fee():
    return Decimal("500.00")