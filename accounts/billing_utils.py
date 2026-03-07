from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

def calc_ipd_days(admission):
    today = timezone.now().date()
    start = admission.admitted_at.date()

    stay_days = (today - start).days + 1
    stay_days = max(stay_days, 1)

    ward_cost = (admission.ward.cost_per_day or Decimal("0")) * stay_days if admission.ward else Decimal("0")
    icu_cost = Decimal("0")
    ventilator_cost = Decimal("0")

    if admission.ward:
        if getattr(admission, "is_icu", False):
            icu_cost = (admission.ward.icu_extra or Decimal("0")) * stay_days

        if getattr(admission, "on_ventilator", False):
            ventilator_cost = (admission.ward.ventilator_cost or Decimal("0")) * stay_days

    total = ward_cost + icu_cost + ventilator_cost

    return {
        "days": stay_days,
        "ward_cost": ward_cost,
        "icu_cost": icu_cost,
        "ventilator_cost": ventilator_cost,
        "total": total,
    }

def opd_appointment_fee():
    return Decimal("500.00")