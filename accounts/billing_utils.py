from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

def calculate_ipd_bill(admission):

    today = timezone.now()

    stay_days = (today.date() - admission.admitted_at.date()).days + 1

    ward_cost = admission.ward.cost_per_day * stay_days

    icu_cost = admission.ward.icu_extra * stay_days

    ventilator_cost = 0

    if admission.on_ventilator:
        ventilator_cost = admission.ward.ventilator_cost * stay_days

    total = ward_cost + icu_cost + ventilator_cost

    return {
        "days": stay_days,
        "ward_cost": ward_cost,
        "icu_cost": icu_cost,
        "ventilator_cost": ventilator_cost,
        "total": total
    }

def opd_appointment_fee():
    return Decimal("500.00")