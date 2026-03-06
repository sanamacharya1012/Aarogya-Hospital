from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone 
from .utils import is_abnormal_value
from .billing_utils import calc_ipd_days, opd_appointment_fee
from datetime import date
from decimal import Decimal

from .decorators import roles_required
from .forms import (
    CreateUserForm, LoginForm, PatientForm, AdmissionForm, AppointmentForm,
    EMRForm, VitalsForm, PrescriptionFormSet, AssignDoctorForm, Specialization, UserUpdateForm, 
    LabOrderForm, LabOrderItemFormSet, LabResultFormSet, LabTestTypeForm, PaymentForm, InvoiceAdjustmentForm
)

from .models import  (
    Patient, Admission, Bed, Appointment, EMR, Department, LabOrder, LabTestType, BillingInvoice, BillingInvoiceItem, BillingPayment, 
    WardTariff
)
from django.db import transaction
from django.db.models import Q
from django.db.models import Count
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.http import HttpResponse
from django.template.loader import render_to_string
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm

User = get_user_model()
# Create your views here.
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    form = LoginForm(request.POST or None)

    if  request.method =="POST" and form.is_valid():
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')

        user = authenticate(request, username=username, password=password)

        if user is  None:
           messages.error(request, "Invalid username or password")
        else:
            login(request, user)
            return redirect('dashboard')
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard_view(request):
    role = getattr(request.user, "role", "")

    today = date.today()

    if role == "DOCTOR":

        qs_today = Appointment.objects.filter(
            doctor=request.user,
            appointment_date=today
        )
        today_my_scheduled = Appointment.objects.filter(
            doctor=request.user, status=Appointment.Status.SCHEDULED
        ).count()

        my_today = Appointment.objects.filter(
            doctor=request.user, appointment_date=today).count()

        my_completed = Appointment.objects.filter(
            doctor=request.user, status=Appointment.Status.COMPLETED
        ).count()
        
        my_cancelled = Appointment.objects.filter(
            doctor=request.user, status=Appointment.Status.CANCELLED
        ).count()
        today_list = qs_today.select_related("patient").order_by("appointment_time")

        now_time = timezone.localtime().time()
        next_appointment = qs_today.filter(
            status=Appointment.Status.SCHEDULED,
            appointment_time__gte=now_time
        ).select_related("patient").order_by("appointment_time").first()

        today = timezone.localdate()

        lab_qs = LabOrder.objects.select_related(
            "patient"
            ).filter(
            patient__assigned_doctor=request.user
        )
        
        lab_total = lab_qs.count()

        lab_today = lab_qs.filter(
            created_at__date=today
        ).count()

        lab_requested = lab_qs.filter(
            status=LabOrder.Status.REQUESTED
        ).count()

        lab_in_progress = lab_qs.filter(
            status=LabOrder.Status.IN_PROGRESS
        ).count()

        lab_completed = lab_qs.filter(
            status=LabOrder.Status.COMPLETED
        ).count()

        # Table data for dashboard
        today_lab_orders = lab_qs.filter(
            created_at__date=today
        ).order_by("-created_at")

        return render(request, "accounts/dashboard_doctor.html", {
            "my_today": my_today,
            "today_my_scheduled": today_my_scheduled,
            "my_completed": my_completed,
            "my_cancelled": my_cancelled,
            "today_list": today_list,
            "next_appointment": next_appointment,
            "lab_total": lab_total,
            "lab_today": lab_today,
            "lab_requested": lab_requested,
            "lab_in_progress": lab_in_progress,
            "lab_completed": lab_completed,
            "today_lab_orders": today_lab_orders,
            "today": today,
        })
    



    total_patients = Patient.objects.count()
    admitted_count = Admission.objects.filter(
        status=Admission.Status.ADMITTED
    ).count()
    

    discharged_count = Admission.objects.filter(
        status=Admission.Status.DISCHARGED
    ).count()

    total_doctors = User.objects.filter(
        role="DOCTOR", is_active=True
    ).count()

    total_nurses = User.objects.filter(
        role="NURSE", is_active=True
    ).count()

    available_beds = Bed.objects.filter(
        status=Bed.Status.AVAILABLE
    ).count()

    occupied_beds = Bed.objects.filter(
        status=Bed.Status.OCCUPIED
    ).count()

    maintenace_beds = Bed.objects.filter(
        status=Bed.Status.MAINTENANCE
    ).count()

    doctor_by_specialization = (
        User.objects
        .filter(role="DOCTOR", is_active=True)
        .values("specialization__name")
        .annotate(total=Count("id"))
        .order_by("specialization__name")
    )

    today = timezone.localdate()

    # Base queryset (role-based restriction for Doctor /Nurse)
    lab_qs = LabOrder.objects.select_related("patient")

    #lab cards
    lab_total = lab_qs.count()
    lab_today = lab_qs.filter(created_at__date=today).count()

    lab_requested = lab_qs.filter(status=LabOrder.Status.REQUESTED).count()
    lab_sample_collected = lab_qs.filter(status=LabOrder.Status.SAMPLE_COLLECTED).count()
    lab_in_progress = lab_qs.filter(status=LabOrder.Status.IN_PROGRESS).count()
    lab_completed = lab_qs.filter(status=LabOrder.Status.COMPLETED).count()
    lab_cancelled = lab_qs.filter(status=LabOrder.Status.CANCELLED).count()

    return render(
        request,
        "accounts/dashboard.html",
        {
           "today": today,
           "total_patients": total_patients,
            "admitted_count": admitted_count,
            "discharged_count": discharged_count,
            "total_doctors": total_doctors,
            "total_nurses": total_nurses,
            "available_beds": available_beds,
            "occupied_beds": occupied_beds,
            "maintenace_beds": maintenace_beds,
            "doctor_by_specialization": doctor_by_specialization,
            "lab_total": lab_total,
            "lab_today": lab_today,
            "lab_requested": lab_requested,
            "lab_sample_collected": lab_sample_collected,
            "lab_in_progress": lab_in_progress,
            "lab_completed": lab_completed,
            "lab_cancelled": lab_cancelled
        },
    )

@login_required
@roles_required('ADMIN')
def create_user_view(request):
    form = CreateUserForm(request.POST or None)
    if request.method == "POST":
        form = CreateUserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "User created successfully")
            return redirect("dashboard")

        # Only show errors on POST when invalid
        print("CREATE USER ERRORS:", form.errors)
        messages.error(request, "Please fix the errors below.")
    else:
        form = CreateUserForm()
    return render(request, 'accounts/create_user.html', {'form': form})

@login_required
@roles_required("ADMIN", "RECEPTION", "DOCTOR", "NURSE")
def patient_list_view(request):
    q = (request.GET.get("q") or "").strip()

    patients = Patient.objects.all()

    # 🔐 Doctor & Nurse see only assigned patients
    if request.user.role in ["DOCTOR", "NURSE"]:
        patients = patients.filter(assigned_doctor=request.user)

    if q:
        patients = patients.filter(
            Q(patient_id__icontains=q) |
            Q(full_name__icontains=q) |
            Q(phone_number__icontains=q)
        )

    patients = patients.order_by("-created_at")

    return render(request, "accounts/patient_list.html", {
        "patients": patients,
        "q": q,
    })


@login_required
@roles_required('ADMIN', 'RECEPTION')
def patient_create_view(request):
    form = PatientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        patient = form.save()
        messages.success(request, f"Patient created: {patient.patient_id}")
        return redirect('patient_list')
    return render(request, 'accounts/patient_create.html', {'form': form})

@login_required
@roles_required("ADMIN")
def user_list_view(request):
    q = (request.GET.get("q") or "").strip()
    role = (request.GET.get("role") or "").strip()
    department_id = (request.GET.get("department") or "").strip()
    specialization_id = (request.GET.get("specialization") or "").strip()
    active = (request.GET.get("active") or "").strip()

    users = User.objects.all().select_related("department", "specialization").order_by("-id")

    #search

    if q:
        users = users.filter(
            Q(full_name__icontains=q) |
            Q(username__icontains=q) |
            Q(email__icontains=q) |
            Q(phone_number__icontains=q)
        )

    #filters
    if role:
        users = users.filter(role=role)
    
    if department_id:
        users = users.filter(department_id=department_id)

    if specialization_id:
        users = users.filter(specialization_id=specialization_id)

    if active in ["0", "1"]:
        users = users.filter(is_active=(active =="1"))
    
    #pagination
    paginator = Paginator(users, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    #for dropdowns
    departments = Department.objects.all().order_by("name")
    specilizations = Specialization.objects.select_related("department").order_by("name")

    #choices for  role 
    role_choices = getattr(User, "Role", None)
    if role_choices:
        role_choices = User.Role.choices
    else:
        role_choices=[
            ('ADMIN', 'Admin'),
            ('DOCTOR', 'Doctor'),
            ('NURSE', 'Nurse'),
            ('RECEPTION', 'Reception'),
            ('LAB', 'Lab'),
            ('PHARMACY', 'Pharmacy'),
            ('HR', 'HR'),
        ]
    
    return render(request, "accounts/user_list.html", {
        "page_obj": page_obj,
        "q": q,
        "role": role,
        "department_id": department_id,
        "specialization_id": specialization_id,
        "active": active,
        "role_choices": role_choices,
        "departments": departments,
        "specializations": specilizations,
    })


@login_required
@roles_required("ADMIN")
def user_detail_view(request, user_id):
    staff = get_object_or_404(User, id=user_id)
    form = UserUpdateForm(request.POST or None, instance=staff)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request,"User updated successfully.")
            return redirect("user_detail", usere_id=staff.id)
        else:
            messages.error(request, "Please fix the errors below.")
    
    return render(request, "accounts/user_detail.html", {"staff": staff, "form": form})

@login_required
@roles_required("ADMIN")
@require_POST
def user_toggle_active_view(request, user_id):
    staff = get_object_or_404(User, id=user_id)

    # prevent disabling yourself
    if staff.id == request.user.id:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("user_detail", user_id=staff.id)

    staff.is_active = not staff.is_active
    staff.save(update_fields=["is_active"])

    messages.success(request, f"{staff.username} is now {'Active' if staff.is_active else 'Inactive'}.")
    return redirect("user_detail", user_id=staff.id)

@login_required
@roles_required("ADMIN", "RECEPTION", "DOCTOR", "NURSE")
def admit_patient_view(request, patient_id):
    patient = get_object_or_404(Patient, patient_id=patient_id)

    active = Admission.objects.filter(patient=patient, status=Admission.Status.ADMITTED).first()
    if active:
        messages.warning(request, "Patient is already admitted.")
        return redirect("patient_list")

    form = AdmissionForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            admission = form.save(commit=False)
            admission.patient = patient
            admission.status = Admission.Status.ADMITTED
            admission.admitted_at = timezone.now()

            # lock bed row so two users can't allocate same bed
            if admission.bed_id:
                bed = Bed.objects.select_for_update().get(id=admission.bed_id)
                if bed.status != Bed.Status.AVAILABLE:
                    messages.error(request, "Bed just became unavailable. Please select another.")
                    return render(request, "accounts/admit_patient.html", {"patient": patient, "form": form})
                bed.status = Bed.Status.OCCUPIED
                bed.save()

            admission.save()

        messages.success(request, f"Admitted: {patient.patient_id}")
        return redirect("patient_detail", patient_id=patient.patient_id)

    return render(request, "accounts/admit_patient.html", {"patient": patient, "form": form})

@login_required
@roles_required("ADMIN", "RECEPTION")
def assign_doctor_view(request, patient_id):
    patient = get_object_or_404(Patient, patient_id=patient_id)
    form = AssignDoctorForm(request.POST or None, instance=patient)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Doctor assigned successfully.")
        return redirect("patient_detail", patient_id=patient.patient_id)
    return render(request, "accounts/assign_doctor.html", {"patient": patient, "form": form})

@login_required
@roles_required('ADMIN', 'RECEPTION', 'DOCTOR', 'NURSE')
def discharge_patient_view(request, admission_id):
    admission = get_object_or_404(Admission, id=admission_id)

    # already discharged
    if admission.status == Admission.Status.DISCHARGED:
        messages.info(request, "Already Discharged")
        return redirect('patient_detail', patient_id=admission.patient.patient_id)
    
    # check invoice due amount
    invoice = BillingInvoice.objects.filter(admission=admission).order_by("-id").first()

    if invoice  and invoice.due_amount > 0:
        messages.error(request, "Cannot discharge. Billing not cleared.")
        return redirect('patient_detail', patient_id=admission.patient.patient_id)
    
    if request.method == "POST":
        with transaction.atomic():
           # Free the bed 
            if admission.bed:
                bed = Bed.objects.select_for_update().get(id=admission.bed_id)
                bed.status = Bed.Status.AVAILABLE
                bed.save()
                
        # Mark admission discharged
        admission.status = Admission.Status.DISCHARGED
        admission.discharged_at = timezone.now()
        admission.save()
        messages.success(request, f"Discharged: {admission.patient.patient_id}")
        return redirect('patient_detail', patient_id=admission.patient.patient_id)
    return render(request, 'accounts/discharge_patient.html', {'admission': admission})

@login_required
@roles_required("ADMIN", "RECEPTION", "DOCTOR", "NURSE")
def patient_detail_view(request, patient_id):
    patient = get_object_or_404(Patient, patient_id=patient_id)

    # 🔐 Restrict doctor & nurse
    if request.user.role in ["DOCTOR", "NURSE"]:
        if patient.assigned_doctor_id != request.user.id:
            messages.error(request, "You are not allowed to view this patient.")
            return redirect("patient_list")

    admissions = patient.admissions.all().order_by("-admitted_at")
    active_admission = admissions.filter(status="ADMITTED").first()

    return render(request, "accounts/patient_detail.html", {
        "patient": patient,
        "admissions": admissions,
        "active_admission": active_admission,
    })
    
    return render(request, 'accounts/patient_detail.html', {'patient': patient, 'admissions': admissions, 'active_admission': active_admission})



@login_required
def available_bed_api(request):
    ward_id = request.GET.get("ward_id")
    if not ward_id:
        return JsonResponse({"beds": []})
    
    beds = (
        Bed.objects
        .filter(ward_id=ward_id, status=Bed.Status.AVAILABLE)
        .order_by("bed_number")
        .values("id", "bed_number")
    )

    return JsonResponse({"beds": list(beds)})

@login_required
def appointment_list_view(request):
    qs = Appointment.objects.select_related("patient", "doctor").all()

    # ✅ IMPORTANT: GET param name must match template select name
    selected_spec = (request.GET.get("specialization") or "").strip()

    # Filter by specialization (works only if doctor has specialization set)
    if selected_spec:
        qs = qs.filter(doctor__specialization_id=selected_spec)

    # Doctor sees only their own appointments
    if request.user.role == "DOCTOR":
        qs = qs.filter(doctor=request.user)

    qs = qs.order_by("-appointment_date", "-appointment_time")

    specializations = Specialization.objects.select_related("department").order_by("name")

    # Debug (optional)
    # print("selected_spec:", selected_spec, "count:", qs.count())

    return render(request, "accounts/appointment_list.html", {
        "appointments": qs,
        "specializations": specializations,
        "selected_spec": selected_spec,  # keep as string
    })

@login_required
@roles_required('ADMIN', 'RECEPTION')
def appointment_create_view(request):
    form = AppointmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Appointment created successfully")
        return redirect("appointment_list")
    return render(request, "accounts/appointment_create.html", {"form": form})

@login_required
@roles_required('DOCTOR')
def appointment_complete_view(request, appointment_id):
    appt = get_object_or_404(Appointment, id=appointment_id)

    if appt.doctor_id != request.user.id:
        messages.error(request, "You can only complete your own appointments.")
        return redirect("appointment_list")

    if appt.status != Appointment.Status.SCHEDULED:
        messages.info(request, "Appointment is not in scheduled status.")
        return redirect("appointment_list")

    if request.method == "POST":
        appt.status = Appointment.Status.COMPLETED
        appt.save()
        messages.success(request, "Appointment marked as completed.")
        return redirect("appointment_list")

    return render(request, "accounts/appointment_confirm.html", {
        "appt": appt,
        "action": "complete",
        "title": "Mark appointment as Completed?",
        "btn_class": "btn-success",
        "btn_text": "Yes, Complete",
    })

@login_required
@roles_required('ADMIN', 'RECEPTION')
def appointment_cancel_view(request, appointment_id):
    appt = get_object_or_404(Appointment, id=appointment_id)

    if appt.status == Appointment.Status.COMPLETED:
        messages.error(request, "Cannot cancel completed appointment.")
        return redirect("appointment_list")
    
    if appt.status == Appointment.Status.CANCELLED:
        messages.info(request, "Appointment is already cancelled.")
        return redirect("appointment_list")
    
    if request.method == "POST":
        appt.status = Appointment.Status.CANCELLED
        appt.save()
        messages.success(request, "Appointment cancelled successfully.")
        return redirect("appointment_list")
    
    return render(request, "accounts/appointment_confirm.html", {
        "appt": appt,
        "action": "cancel",
        "title": "Cancel this Appointment?",
        "btn_class": "btn-danger",
        "btn_text": "Yes, Cancel"
    })

@login_required
@roles_required("DOCTOR")
def emr_create_view(request, patient_id):
    patient = get_object_or_404(Patient, patient_id=patient_id)

    emr_form = EMRForm(request.POST or None)
    vitals_form = VitalsForm(request.POST or None)
    formset = PrescriptionFormSet(request.POST or None, prefix="rx")

    if request.method == "POST":
        if emr_form.is_valid() and vitals_form.is_valid() and formset.is_valid():
            emr = emr_form.save(commit=False)
            emr.patient = patient
            emr.doctor = request.user
            emr.save()

            vitals = vitals_form.save(commit=False)
            vitals.emr = emr
            vitals.save()

            formset.instance = emr
            formset.save()

            messages.success(request, "EMR saved with vitals and prescription.")
            return redirect("patient_detail", patient_id=patient.patient_id)
        else:
            messages.error(request, "Please fix the errors below.")
            print("EMR ERRORS:", emr_form.errors)
            print("VITALS ERRORS:", vitals_form.errors)
            print("RX ERRORS:", formset.errors)

    return render(
        request,
        "accounts/emr_form.html",
        {"emr_form": emr_form, "vitals_form": vitals_form, "formset": formset, "patient": patient, "mode": "create"},
    )

@login_required
@roles_required("DOCTOR")
def emr_update_view(request, emr_id):
    emr = get_object_or_404(EMR, id=emr_id)

    # Only creator doctor can edit
    if emr.doctor_id != request.user.id:
        messages.error(request, "You can only edit EMR you created.")
        return redirect("patient_detail", patient_id=emr.patient.patient_id)

    emr_form = EMRForm(request.POST or None, instance=emr)

    vitals_obj = getattr(emr, "vitals", None)
    vitals_form = VitalsForm(request.POST or None, instance=vitals_obj)

    formset = PrescriptionFormSet(request.POST or None, instance=emr, prefix="rx")

    if request.method == "POST":
        if emr_form.is_valid() and vitals_form.is_valid() and formset.is_valid():
            emr_form.save()

            vitals = vitals_form.save(commit=False)
            vitals.emr = emr
            vitals.save()

            formset.save()

            messages.success(request, "EMR updated.")
            return redirect("patient_detail", patient_id=emr.patient.patient_id)
        else:
            messages.error(request, "Please fix the errors below.")
            print("EMR ERRORS:", emr_form.errors)
            print("VITALS ERRORS:", vitals_form.errors)
            print("RX ERRORS:", formset.errors)

    return render(
        request,
        "accounts/emr_form.html",
        {
            "patient": emr.patient,
            "emr_form": emr_form,
            "vitals_form": vitals_form,
            "formset": formset,
            "mode": "edit",
            "emr": emr,
        },
    )

@login_required
@roles_required("ADMIN", "RECEPTION", "DOCTOR", "NURSE")
def emr_search_view(request):
    q = (request.GET.get("q") or "").strip()
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    doctor_id = (request.GET.get("doctor_id") or "").strip()

    results = EMR.objects.select_related("patient", "doctor")

    if q:
        results = results.filter(
            Q(diagnosis__icontains=q) |
            Q(patient__patient_id__icontains=q) |
            Q(patient__full_name__icontains=q)
        )
        

    if date_from:
        results = results.filter(created_at__date__gte=date_from)

    if date_to:
        results = results.filter(created_at__date__lte=date_to)

    # Admin/Reception/Nurse can filter by doctor
    doctors = []
    if request.user.role != "DOCTOR":
        doctors = get_user_model().objects.filter(role="DOCTOR", is_active=True)
        if doctor_id:
            results = results.filter(doctor_id=doctor_id)

    results = results.order_by("-created_at")[:300]

    

    return render(
        request,
        "accounts/emr_search.html",
        {
            "q": q,
            "date_from": date_from,
            "date_to": date_to,
            "doctor_id": doctor_id,
            "doctors": doctors,
            "results": results,
        },
    )


@login_required
@roles_required("ADMIN", "RECEPTION", "DOCTOR", "NURSE")
def emr_pdf_view(request, emr_id):
    emr = get_object_or_404(
        EMR.objects.select_related("patient", "doctor"),
        id=emr_id
    )

    if request.user.role == "DOCTOR" and emr.doctor_id != request.user.id:
        messages.error(request, "You can only print your own EMR")
        return redirect("emr_search")

    # ✅ If prescription is TextField/CharField:
    rx_text = (emr.prescription or "").strip()
    rx_items = [x.strip() for x in rx_text.splitlines() if x.strip()]

    vitals = getattr(emr, "vitals", None)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="EMR_{emr.patient.patient_id}_{emr.id}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    x = 20 * mm
    y = height - 20 * mm
    bottom_margin = 20 * mm

    def ensure_space(dy):
        nonlocal y
        if y - dy < bottom_margin:
            p.showPage()
            y = height - 20 * mm

    def line(txt, dy=7 * mm, bold=False):
        nonlocal y
        ensure_space(dy)
        p.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        p.drawString(x, y, txt)
        y -= dy

    # ✅ PDF content (correct indentation)
    line("Hospital Management System - EMR", bold=True, dy=9 * mm)
    line(f"Patient: {emr.patient.full_name} ({emr.patient.patient_id})")
    line(f"Doctor: {emr.doctor.full_name}")
    line(f"Date/Time: {emr.created_at.strftime('%Y-%m-%d %H:%M')}")
    line("")

    line("Vitals", bold=True)
    if vitals:
        bp = "-"
        if getattr(vitals, "bp_systolic", None) and getattr(vitals, "bp_diastolic", None):
            bp = f"{vitals.bp_systolic}/{vitals.bp_diastolic}"

        line(
            f"BP: {bp}  "
            f"Temp: {getattr(vitals, 'temperature_c', '-') or '-'} C  "
            f"Pulse: {getattr(vitals, 'pulse', '-') or '-'} bpm  "
            f"SpO2: {getattr(vitals, 'spo2', '-') or '-'}%  "
            f"Weight: {getattr(vitals, 'weight_kg', '-') or '-'} kg",
            dy=6 * mm
        )
    else:
        line("No vitals recorded.")
    line("")

    line("Diagnosis", bold=True)
    for chunk in (emr.diagnosis or "-").splitlines():
        line(chunk, dy=6 * mm)
    line("")

    if emr.symptoms:
        line("Symptoms", bold=True)
        for chunk in emr.symptoms.splitlines():
            line(chunk, dy=6 * mm)
        line("")

    line("Prescription", bold=True)
    if not rx_items:
        line("No medicines.")
    else:
        for i, item in enumerate(rx_items, 1):
            # Wrap long lines safely
            text = f"{i}. {item}"
            for start in range(0, len(text), 110):
                line(text[start:start + 110], dy=6 * mm)

    p.showPage()
    p.save()
    return response

@login_required
@roles_required("ADMIN")
def specializations_api(request):
    dept_id = request.GET.get("department_id")
    if not dept_id:
        return JsonResponse({"items": []})
    
    items = (
        Specialization.objects
        .filter(department_id=dept_id)
        .order_by("name")
        .values("id", "name")
    )

    return JsonResponse({"items": list(items)})

def can_access_patient(request, patient):
    if request.user.role in["DOCTOR", "NURSE"]:
        return patient.assigned_doctor_id == request.user.id
    return True

@login_required
@roles_required("ADMIN", "RECEPTION", "DOCTOR", "NURSE", "LAB")
def lab_order_list_view(request):
    q = (request.GET.get("q") or "").strip()

    orders = LabOrder.objects.select_related("patient", "requested_by").order_by("-id")

    if request.user.role in ["DOCTOR", "NURSE"]:
        orders = orders.filter(patient__assigned_doctor=request.user)

    if q:
        orders = orders.filter(
            Q(patient__patient_id__icontains=q) |
            Q(patient__full_name__icontains=q) |
            Q(status__icontains=q)
        )

    return render(request, "accounts/lab_order_list.html", {"orders": orders, "q": q})

@login_required
@roles_required("ADMIN","RECEPTION","DOCTOR", "LAB")
def lab_order_create_view(request, patient_id):
    patient = get_object_or_404(Patient, patient_id=patient_id)

    if not can_access_patient(request, patient):
        messages.error(request,"You are not allowed to create lab orders for this patient.")
        return redirect("patient_list")
    order_form = LabOrderForm(request.POST or None)
    formset = LabOrderItemFormSet(request.POST or None, prefix="items")

    if request.method == "POST":
        if order_form.is_valid() and formset.is_valid():
            order = order_form.save(commit=False)
            order.patient = patient
            order.requested_by = request.user
            order.save()

            formset.instance = order
            formset.save()

            messages.success(request, "Lab order created.")
            return redirect("lab_order_detail", order_id=order.id)
        messages.error(request, "Please fix tyhe errors below.")

    return render(request, "accounts/lab_order_form.html",{
        "patient": patient,
        "order_form": order_form,
        "formset": formset,
    })

@login_required
@roles_required("ADMIN", "RECEPTION", "DOCTOR", "NURSE", "LAB")
def lab_order_detail_view(request, order_id):
    order = get_object_or_404(
        LabOrder.objects.select_related("patient", "requested_by"), id=order_id
    )
    if not can_access_patient(request, order.patient):
        messages.error(request, "You are not allowed to view this lab order.")
        return redirect("lab_order_list")
    return render(request, "accounts/lab_order_detail.html", {"order": order})

@login_required
@roles_required("ADMIN", "RECEPTION", "LAB")
def lab_order_status_view(request, order_id, status):
    order = get_object_or_404(LabOrder, id=order_id)

    allowed = [
        LabOrder.Status.SAMPLE_COLLECTED,
        LabOrder.Status.IN_PROGRESS,
        LabOrder.Status.COMPLETED,
        LabOrder.Status.CANCELLED,
    ]
    if status not in allowed:
        messages.error(request, "Invalid status.")
        return redirect("lab_order_detail", order_id=order_id)
    
    order.status = status
    order.save(update_fields=["status"])
    messages.success(request, f"Order Status updated: { status}.")
    return redirect("lab_order_detail", order_id=order.id)

@login_required
@roles_required("ADMIN", "RECEPTION", "LAB")
def lab_result_entry_view(request, order_id):
    order = get_object_or_404(LabOrder.objects.select_related("patient"), id=order_id)

    formset = LabResultFormSet(request.POST or None, instance=order, prefix="res")

    if request.method == "POST":
        if formset.is_valid():
            formset.save()

            # auto set abnormal based on normal range
            for it in order.items.select_related("test_type").all():
                it.is_abnormal = is_abnormal_value(it.result_value, it.test_type.normal_range)
                it.save(update_fields=["is_abnormal"])

            order.status = LabOrder.Status.COMPLETED
            order.save(update_fields=["status"])
            messages.success(request, "Results saved and order marked completed.")
            return redirect("lab_order_detail", order_id=order.id)
        messages.error(request,"Please fix the errors below.")
    return render(request, "accounts/lab_result_entry.html", {"order": order, "formset": formset})

@login_required
@roles_required("ADMIN")
def lab_testtype_list_view(request):
    q = (request.GET.get("q") or "").strip()

    qs = LabTestType.objects.select_related("department").order_by("name")
    if q:
        qs =qs.filter(name__icontains=q)

    paginator = Paginator(qs , 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "accounts/testtype_list.html", {"page_obj": page_obj, "q": q})

@login_required
@roles_required("ADMIN")
def lab_testtype_create_view(request):
    form = LabTestTypeForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Lab test type created.")
            return  redirect("lab_testtype_list")
        messages.error(request, "Please fix the errors below.")
    return render(request, "accounts/testtype_form.html", {"form": form, "mode": "create"})

@login_required
@roles_required("ADMIN")
def lab_testtype_edit_view(request, test_id):
    obj = get_object_or_404(LabTestType, id=test_id)
    form = LabTestTypeForm(request.POST or None, instance=obj)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Lab test type updated.")
            return redirect("lab_testtype_list")
        messages.error(request, "Please fix the errors below.")
    return render(request, "account/testtype_form.html", {"form": form, "mode": "edit", "obj": obj })

@login_required
@roles_required("ADMIN")
@require_POST
def lab_testtype_delete_view(request, test_id):
    obj = get_object_or_404(LabTestType, id=test_id)
    obj.delete()
    messages.success(request, "Lab test type deleted.")
    return redirect("lab_testtype_list")

@login_required
@roles_required("ADMIN", "RECEPTION", "LAB", "DOCTOR", "NURSE")
def lab_order_pdf_view(request, order_id):
    order = get_object_or_404(LabOrder.objects.select_related("patient", "requested_by"), id=order_id)

    # Doctor/Nurse only assigned patients
    if request.user.role in ["DOCTOR", "NURSE"]:
        if order.patient.assigned_doctor_id != request.user.id:
            messages.error(request, "You are not allowed to view this report.")
            return redirect("lab_order_list")
        
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] =f'inline; filename="lab_order_{order.id}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    y = height - 2 * cm 

    #Header
    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm, y, "Hospital Lab Report")
    y -= 0.8 * cm

    p.setFont("Helvetica", 10)
    p.drawString(2 * cm, y, f"Order #: {order.id}   Status: {order.status}")
    y -= 0.6 * cm
    p.drawString(2 * cm, y, f"Patient #: {order.patient.full_name} ({order.patient.patient_id})")
    y -= 0.6 * cm
    p.drawString(2 * cm, y, f"Requested By: {order.requested_by.full_name if order.requested_by else '-'}")
    y -= 0.6 * cm
    p.drawString(2 * cm, y, f"Date: {order.created_at.strftime('%Y-%m-%d %H:%M')}")
    y -= 1.0 * cm

    #Notes
    if order.notes:
        p.setFont("Helvetica-Bold", 10)
        p.drawString(2 * cm, y, "Notes:")
        y -= 0.5 * cm
        p.setFont("Helvetica", 10)
        p.drawString(2 * cm, y, order.notes[:120])
        y -= 0.8 * cm

    # Table headers
    p.setFont("Helvetica-Bold", 10)
    p.drawString(2 * cm, y, "Test")
    p.drawString(8 * cm, y, "Result")
    p.drawString(12 * cm, y, "Normal Range")
    p.drawString(16.5 * cm, y, "Flag")
    y -= 0.4 * cm
    p.line(2 * cm, y, width - 2 * cm, y)
    y -= 0.6 * cm

    #rows
    p.setFont("Helvetica-Bold", 10)
    for it in order.items.select_related("test_type").all():
        if y < 2 * cm:
            p.showPage()
            y - height - 2* cm
            p.setFont("Helvetica-Bold", 10)
            p.drawString(2 * cm, y, "Test")
            p.drawString(8 * cm, y, "Result")
            p.drawString(12 * cm, y, "Normal Range")
            p.drawString(16.5 * cm, y, "Flag")
            y -= 0.4 * cm
            p.line(2 * cm, y. width - 2 * cm, y)
            y -= 0.6 * cm
            p.setFont("Helvetica", 10)
        test_name = it.test_type.name
        result = it.result_value or "-"
        normal = it.test_type.normal_range or "-"
        flag = "ABN" if it.is_abnormal else ""

        p.drawString(2 * cm, y, test_name[:35])
        p.drawString(8 * cm, y, str(result)[:18])
        p.drawString(12 * cm, y, str(normal)[:22])
        p.drawString(16.5 * cm, y, flag)
        y -= 0.6 * cm
    
    y -= 0.6 * cm
    p.setFont("Helvetica", 9)
    p.drawString(2 * cm, y, "Generated by HMS • Lab Module")

    p.showPage()
    p.save()
    return response

@login_required
@roles_required("ADMIN", "CASHIER", "ACCOUNTANT")
def invoice_list_view(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    ptype = (request.GET.get("ptype") or "").strip()

    qs = BillingInvoice.objects.select_related("patient").order_by("-id")

    if q:
        qs = qs.filter(
            Q(invoice_no__icontains=q) |
            Q(patient__patient_id__icontains=q) |
            Q(patient__full_name__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if ptype:
        qs = qs.filter(patient_type=ptype)

    return render(request, "accounts/invoice_list.html", {
        "invoices": qs,
        "q": q,
        "status": status,
        "ptype": ptype,
        "status_choices": BillingInvoice.Status.choices,
        "ptype_choices": BillingInvoice.PatientType.choices,
    })

@login_required
@roles_required("ADMIN", "CASHIER", "ACCOUNTANT")
def invoice_detail_view(request, invoice_id):
    inv = get_object_or_404(BillingInvoice.objects.select_related("patient"), id=invoice_id)

    adjust_form = InvoiceAdjustmentForm(request.POST or None, instance=inv)

    if request.method == "POST":
        # only admin/accountact should adjust
        if request.user.role not in ["ADMIN", "ACCOUNTANT"]:
            messages.error(request, "Only Admin/accountant can update tax/discount")
            return redirect("invoice_detail", invoice_id=inv.id)
        
        if adjust_form.is_valid():
            adjust_form.save()
            # update status
            _update_invoice_status(inv)
            messages.success(request, "Invoice updated")
            return redirect("invoice_detail", invoice_id=inv.id)
        messages.error(request, "fix errors below")

    return render(request,"accounts/invoice_detail.html", {"inv": inv, "adjust_form": adjust_form})

def _update_invoice_status(inv: BillingInvoice):
    if inv.status == BillingInvoice.Status.CANCELLED:
        return
    due = inv.due_amount
    if due <= 0:
        inv.staus = BillingInvoice.Status.PAID
    elif inv.paid_amount > 0:
        inv.status = BillingInvoice.Status.PARTIAL
    else:
        inv.status = BillingInvoice.Status.DRAFT
    inv.save(update_fields=["status"])


@login_required
@roles_required("ADMIN", "CASHIER")
def payment_add_view(request, invoice_id):
    inv = get_object_or_404(BillingInvoice, id=invoice_id)
    form = PaymentForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            pay = form.save(commit=False)
            pay.invoice = inv
            pay.received_bg= request.user
            pay.save()

            _update_invoice_status(inv)

            # if IPD invoice paid -> mark admission billing cleared
            if inv.admission and inv.status == BillingInvoice.Status.PAID:
                inv.admission.billing_cleared = True
                inv.admission.save(update_fields=["billing_cleared"])

            messages.success(request, "Payemnt received.")
            return redirect("invoice_detail", invoice_id=inv.id)
        messages.error(request, "Fix errors below.")
    
    return render(request, "accounts/payment_form.html", {"inv": inv, "form": form})

@login_required
@roles_required("ADMIN", "RECEPTION", "CASHIER")
def invoice_create_for_appointment_view(request, appointment_id):
    appt = get_object_or_404(Appointment.objects.select_related("patient", "doctor"), id=appointment_id)

    #avoid duplicate
    existing = BillingInvoice.objects.filter(appointment=appt).first()
    if existing:
        return redirect("invoice_detail", invoice_id=existing.id)
    
    inv = BillingInvoice.objects.create(
        patient=appt.patient,
        patient_type=BillingInvoice.PatientType.OPD,
        appointment=appt,
        created_by=request.user
    )

    BillingInvoiceItem.objects.create(
        invoice=inv,
        description=f"Appointment Fee({appt.doctor.full_name if appt.doctor else 'Doctor'})",
        qty=Decimal("1"),
        unit_price=opd_appointment_fee()
    )

    _update_invoice_status(inv)
    messages.success(request, "Appointment invoice created.")
    return redirect("invoice_detail", invoice_id=inv.id)

@login_required
@roles_required("ADMIN", "RECEPTION", "CASHIER")
def invoice_create_for_lab_view(request, lab_order_id):
    lo = get_object_or_404(LabOrder.objects.select_related("patient"), id=lab_order_id)

    existing = BillingInvoice.objects.filter(lab_order=lo).first()
    if existing:
        return redirect("invoice_detail", invoice_id=existing.id)

    inv = BillingInvoice.objects.create(
        patient=lo.patient,
        patient_type=BillingInvoice.PatientType.OPD,
        lab_order=lo,
        created_by=request.user
    )

    for it in lo.items.select_related("test_type").all():
        price = it.test_type.price or Decimal("0")
        BillingInvoiceItem.objects.create(
            invoice=inv,
            description=f"Lab Test: {it.test_type.name}",
            qty=Decimal("1"),
            unit_price=price,
            lab_test_type=it.test_type
        )

    _update_invoice_status(inv)
    messages.success(request, "Lab invoice created.")
    return redirect("invoice_detail", invoice_id=inv.id)

@login_required
@roles_required("ADMIN", "RECEPTION", "CASHIER")
def invoice_create_for_admission_view(request, admission_id):
    adm = get_object_or_404(
        Admission.objects.select_related("patient", "ward", "bed"),
        id=admission_id
    )

    existing = BillingInvoice.objects.filter(admission=adm).first()
    if existing:
        return redirect("invoice_detail", invoice_id=existing.id)
    
    inv = BillingInvoice.objects.create(
        patient=adm.patient,
        patient_type=BillingInvoice.PatientType.IPD,
        admission=adm,
        created_by=request.user
    )

    tariff, _ = WardTariff.objects.get_or_create(ward=adm.ward)

    days = calc_ipd_days(adm.admitted_at, adm.discharged_at)

    # 1) Basebed/day charge
    BillingInvoiceItem.objects.create(
        invoice=inv,
        description=f"Ward Bed Charge ({adm.ward})",
        qty=Decimal(str(days)),
        unit_price=tariff.bed_charge_per_day,
        bed=adm.bed
    )

    # 2) ICU extra/day
    if adm.is_icu:
        BillingInvoiceItem.objects.create(
            invoice=inv,
            description="ICU EXTRA CHARGE",
            qty=Decimal(str(days)),
            unit_price=tariff.icu_extra_per_day,
            ward=adm.ward,
            bed=adm.bed
        )
    
    # 3) Ventilator extra/day
    if adm.on_ventilator:
        BillingInvoiceItem.objects.create(
            invoice=inv,
            description="Ventoilator Charge",
            qty=Decimal(str(days)),
            unit_price=tariff.ventilator_extra_per_day,
            ward=adm.ward,
            bed=adm.bed
        )

    _update_invoice_status(inv)
    messages.success(request, "IPD invoice created.")
    return redirect("invoice_detail", invoice_id=inv.id)

        
@login_required
@roles_required("ADMIN", "CASHIER", "ACCOUNTANT")
def invoice_pdf_view(request, invoice_id):
    inv = get_object_or_404(BillingInvoice.objects.select_related("patient"), id=invoice_id)

    response = HttpResponse(content_type="application/pfd")
    response["COntent-Dispostion"] = f'inline; filename="{inv.invoice_no}.pdf"'

    p= canvas.Canvas(response, pagesize=A4)
    width, height = A4
    y = height -2 * cm

    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm , y, "HMS Invoice")
    y -= 0.8 * cm

    p.setFont("Helvetica", 10)
    p.drawString(2 * cm, y, f"Invoice: {inv.invoice_no}  Status: {inv.status}")
    y -= 0.6 * cm
    p.drawString(2 * cm, y, f"Patient: {inv.patient.full_name}  ({inv.patient.patient_id})")
    y -= 0.6 * cm
    p.drawString(2 * cm, y, f"Date: {inv.created_at.strftime('%Y-%m-%d %H:%i')}")
    y -= 1.0 * cm

    #Table Header

    p.setFont("Helvetica-Bold", 10)
    p.drawString(2 * cm, y, "Description")
    p.drawString(12 * cm, y, "Qty")
    p.drawString(14 * cm, y, "Rate")
    p.drawString(17 * cm, y, "Total")
    y -= 0.4 * cm
    p.line(2 * cm, y, width -2 * cm, y)
    y -= 0.6 * cm

    p.setFont("Helvetica-Bold", 10)
    for it in inv.item.all():
        if y < 2.5 * cm:
            p.showpage()
            y = height - 2 * cm
            p.setFont("Helvetica-Bold", 10)
            p.drawString(2 * cm, y, "Description")
            p.drawString(12 * cm, y, "Qty")
            p.drawString(14 * cm, y, "Rate")
            p.drawString(17 * cm, y, "Total")
            y -= 0.4 * cm
            p.line(2 * cm, y, width -2 * cm, y)
            y -= 0.6 * cm
            p.setFont("Helvetica", 10)

        p.drawString(2 * cm,y, (it.description or "")[:55])
        p.drawRightString(13.5 * cm, y, f"{it.qty}")
        p.drawRightString(16.5 * cm, y, f"{it.unit_price}")
        p.drawRightString(19.0 * cm, y, f"{it.line_total}")
        y -= 0.55 * cm
    
    y -= 0.2 * cm
    p.line(2 * cm, y, width -2 * cm, y)
    y -= 0.7 * cm

    p.setFont("Helvetica-Bold", 10)
    p.drawRightString(18.0 * cm, y, "Subtotal:")
    p.drawRightString(19.0 * cm, y, f"{inv.subtotal}")
    y -= 0.5 * cm

    p.setFont("Helvetica-Bold", 10)
    p.drawRightString(18.0 * cm, y, "Tax:")
    p.drawRightString(19.0 * cm, y, f"{inv.tax}")
    y -= 0.5 * cm
    p.drawRightString(18.0 * cm, y, "Discount:")
    p.drawRightString(19.0 * cm, y, f"{inv.discount}")
    y -= 0.6 * cm
    
    p.setFont("Helvetica-Bold", 10)
    p.drawRightString(18.0 * cm, y, "Grand Total:")
    p.drawRightString(19.0 * cm, y, f"{inv.grand_total}")
    y -= 0.8 * cm

    p.setFont("Helvetica-Bold", 10)
    p.drawRightString(18.0 * cm, y, "Paid:")
    p.drawRightString(19.0 * cm, y, f"{inv.paid_amount}")
    y -= 0.5 * cm
    p.drawRightString(18.0 * cm, y, "Due:")
    p.drawRightString(19.0 * cm, y, f"{inv.due_amount}")

    p.showPage()
    p.save()
    return response