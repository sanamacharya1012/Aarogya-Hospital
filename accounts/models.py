from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import date
from django.conf import settings
from decimal import Decimal

# Create your models here.

class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name
    
class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        DOCTOR = 'DOCTOR', 'Doctor'
        NURSE = 'NURSE', 'Nurse'
        RECEPTION = 'RECEPTION', 'Reception'
        LAB = 'LAB', 'Lab'
        PHARMACY = 'PHARMACY', 'Pharmacy'
        HR = 'HR', 'HR'
        CASHIER = "CASHIER", "Cashier"
        ACCOUNTANT = "ACCOUNTANT", "Accountant"
    
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(unique=True)

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.RECEPTION)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True
    )

    specialization = models.ForeignKey(
        "Specialization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="doctors"
    )

def __str__(self):
    return  f"{self.username} ({self.role})"


class Patient(models.Model):
    patient_id = models.CharField(max_length=20, unique=True, editable=False)
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True)
    gender = models.CharField(max_length=10, choices=[("MALE", "Male"), ("FEMALE", "Female"), ("OTHER", "Other")], blank=True)
    dob = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    assigned_doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_patients",
        limit_choices_to={"role": "DOCTOR"}
    )

    @property
    def age(self):
        if not self.dob:
            return ""
        today = date.today()
        years = today.year - self.dob.year
        if (today.month, today.day) < (self.dob.month, self.dob.day):
            years -= 1
        return years

    def __str__(self):
        return f"{self.patient_id} - {self.full_name}"

    @staticmethod
    def next_patient_id():
        prefix = "HMS-P"
        with transaction.atomic():
            last =(
                Patient.objects.select_for_update()
                .order_by("-id")
                .first()
            )
            if not last:
                return f"{prefix}0001"
        
            last_num =int(last.patient_id.replace(prefix, ""))
            return f"{prefix}{last_num + 1:04d}"

    def save(self, *args, **kwargs):
        if not self.patient_id:
            self.patient_id = Patient.next_patient_id()
        super().save(*args, **kwargs)

class Ward(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name

class Bed(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        OCCUPIED = 'OCCUPIED', 'Occupied'
        MAINTENANCE = 'MAINTENANCE', 'Maintenance'
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name='beds')
    bed_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)

class Admission(models.Model):
    class Status(models.TextChoices):
        ADMITTED = 'ADMITTED', 'Admitted'
        DISCHARGED = 'DISCHARGED', 'Discharged'
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='admissions')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ADMITTED)

    ward = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True, blank=True)
    bed = models.ForeignKey(Bed, on_delete=models.SET_NULL, null=True, blank=True)

    is_icu = models.BooleanField(default=False)
    on_ventilator = models.BooleanField(default=False)

    reason = models.TextField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    admitted_at = models.DateTimeField(default=timezone.now)
    discharged_at = models.DateTimeField(blank=True, null=True)

    billing_cleared = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.patient.patient_id} ({self.status})"

class Appointment(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    patient = models.ForeignKey("Patient", on_delete=models.CASCADE, related_name="appointments")
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        limit_choices_to={"role": "DOCTOR"},
        related_name="appointments",
    )
    
    appointment_date = models.DateTimeField()
    appointment_time = models.TimeField()

    reason = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)

    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ("doctor", "appointment_date", "appointment_time")
        ordering = ["-appointment_date", "-appointment_time"]

        def __str__(self):
            return f"{self.patient} with Dr. {self.doctor} on {self.appointment_date} {self.appointment_time}"

class EMR(models.Model):
    patient = models.ForeignKey("Patient", on_delete=models.CASCADE, related_name="emr_records")

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "DOCTOR"}
    )

    appointment = models.ForeignKey(
        "Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    diagnosis = models.TextField()
    symptoms = models.TextField(blank=True)
    prescription = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"EMR - {self.patient.patient_id} - {self.created_at.date()}"
    
class Vitals(models.Model):
    emr = models.OneToOneField("EMR", on_delete=models.CASCADE, related_name="vitals")

    bp_systolic = models.PositiveIntegerField(null=True, blank=True)
    bp_diastolic = models.PositiveIntegerField(null=True, blank=True)

    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    pulse = models.PositiveIntegerField(null=True, blank=True)
    spo2 = models.PositiveIntegerField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Vitals for EMR #{self.emr_id}"

class PrescriptionItem(models.Model):
    emr = models.ForeignKey("EMR", on_delete=models.CASCADE, related_name="prescriptions")

    medicine_name = models.CharField(max_length=120)
    strength = models.CharField(max_length=60, blank=True)
    form = models.CharField(max_length=60, blank=True)
    dose = models.CharField(max_length=60, blank=True)
    frequency = models.CharField(max_length=60, blank=True)
    duration = models.CharField(max_length=60, blank=True)
    instructions = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.medicine_name} ({self.emr_id})"
    
class Specialization(models.Model):
    department = models.ForeignKey("Department", on_delete=models.CASCADE, related_name="specializations")
    name = models.CharField(max_length=120)

    class Meta:
        unique_together = ("department", "name")

    def __str__(self):
        return f"{self.name} ({self.department.name})"

class LabTestType(models.Model):
    name = models.CharField(max_length=150, unique=True)
    department = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True, blank=True)
    normal_range = models.CharField(max_length=120, blank=True, default="")
    unit = models.CharField(max_length=40, blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.name

class LabOrder(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        SAMPLE_COLLECTED = "SAMPLE_COLLECTED", "Sample Collected"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
    
    patient = models.ForeignKey("Patient", on_delete=models.CASCADE, related_name="lab_orders")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="lab_requests")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.REQUESTED)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"LabOrder #{ self.id}- { self.patient.patient_id}"

class LabOrderItem(models.Model):
    order = models.ForeignKey(LabOrder, on_delete=models.CASCADE, related_name="items")
    test_type = models.ForeignKey(LabTestType, on_delete=models.PROTECT, related_name="order_items")

    result_value = models.CharField(max_length=120, blank=True, default="")
    result_note = models.CharField(max_length=200, blank=True, default="")
    is_abnormal = models.BooleanField(default=False)

    def __str__(self):
        return f"{ self.order_id } - { self.test_type.name}"
    

class WardTariff(models.Model):
    ward = models.OneToOneField("Ward", on_delete=models.CASCADE, related_name="tariff")

    bed_charge_per_day = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # icu pricing
    is_icu = models.BooleanField(default=False)
    icu_extra_per_day = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Ventilator Pricing
    ventilator_extra_per_day = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.ward} Tariff"
    
class BillingInvoice(models.Model):
    class PatientType(models.TextChoices):
        OPD = "OPD", "Opd"
        IPD = "IPD", "Ipd"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PARTIAL = "PARTIAL", "Partial"
        PAID = "PAID", "Paid"
        CANCELLED = "CANCELLED", "Cancelled"

    invoice_no = models.CharField(max_length=30, unique=True, blank=True)

    patient = models.ForeignKey("Patient", on_delete=models.CASCADE, related_name="invoices")
    patient_type = models.CharField(max_length=10, choices=PatientType.choices, default=PatientType.OPD)

    appointment = models.ForeignKey("Appointment", on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    lab_order = models.ForeignKey("LabOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    admission = models.ForeignKey("Admission", on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")

    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)

    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_invoices")
    created_at = models.DateTimeField(auto_now_add=True)

    def savae(self, *args, **kwargs):
        if not self.invoice_no:
            last = BillingInvoice.objects.order_by("-id").first()
            next_id = (last.id + 1) if last else 1
            self.invoice_no = f"HMS_INV-{next_id:04d}"
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return sum((i.line_total for i in self.item.all()), Decimal("0"))
    
    @property
    def grand_total(self):
        total = self.subtotal + (self.tax or 0) - (self.discount or 0)
        return total if total > 0 else Decimal("0")
    
    @property
    def paid_amount(self):
        return sum((p.amount for p in self.payments.all()), Decimal("0"))
    
    @property
    def due_amount(self):
        due = self.grand_total - self.paid_amount
        return due if due > 0 else Decimal("0")

class BillingInvoiceItem(models.Model):
    invoice = models.ForeignKey(BillingInvoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=200)
    qty = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    #optional traceability
    lab_test_type = models.ForeignKey("LabTestType", on_delete=models.SET_NULL, null=True, blank=True)
    ward = models.ForeignKey("Ward", on_delete=models.SET_NULL, null=True, blank=True)
    bed = models.ForeignKey("Bed", on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def line_total(self):
        return(self.qty or 0) * (self.unit_price or 0)
    def __str__(self):
        return self.description
    
class BillingPayment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        CARD = "CARD", "Card"
        ESEWA = "ESEWA", "Esewa"
        KHALTI = "KHALTI", "Khalti"
        BANK = "BANK", "Bank Transfer"

    invoice = models.ForeignKey(BillingInvoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.CASH)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="received_payments")
    received_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=200, blank=True, default="")

    def __str__(self):
        return f"{self.invoice.invoice_no} - {self.amount}"

