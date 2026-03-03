from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Patient, Admission, Bed, Appointment, EMR, Vitals, PrescriptionItem, Specialization, LabOrder, LabOrderItem, LabTestType
from django.forms import inlineformset_factory


User = get_user_model()

class CreateUserForm(UserCreationForm):
    email = forms.EmailField(required=True)
    class Meta:
        model = User
        fields = ["full_name", "phone_number", "email", "username", "role", "department", "specialization", "password1", "password2"]
    
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ IMPORTANT:
        # department must NOT be required at field-level,
        # because we will auto-set it for DOCTOR in clean().
        self.fields["department"].required = False
        self.fields["specialization"].required = False

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")
        department = cleaned.get("department")
        specialization = cleaned.get("specialization")

        if role == "DOCTOR":
            if not specialization:
                raise forms.ValidationError("Specialization is required for Doctor.")
            # ✅ auto-fill department from specialization
            cleaned["department"] = specialization.department

        else:
            # ✅ non-doctors must have department
            if not department:
                raise forms.ValidationError("Department is required for this role.")
            # ✅ non-doctors must not have specialization
            cleaned["specialization"] = None

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)

        role = self.cleaned_data.get("role")
        specialization = self.cleaned_data.get("specialization")

        if role == "DOCTOR":
            user.specialization = specialization
            user.department = specialization.department
        else:
            user.specialization = None

        if commit:
            user.save()
        return user
    
class UserUpdateForm(forms.ModelForm):
    class Meta:
        model =User
        fields = ["role", "department", "specialization"]
    
    def  __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Admin can change freely; will validate rules below
        self.fields["department"].required = False
        self.fields["specialization"].required = False

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")
        department = cleaned.get("department")
        specialization = cleaned.get("specialization")

        if role == "DOCTOR":
            if not specialization:
                raise forms.ValidationError("Specialization is required for Doctor.")
            # auto-set department from specialization
            cleaned["department"] = specialization.department

        else:
            # non-doctors require department
            if not department:
                raise forms.ValidationError("Department is required for this role.")
            cleaned["specialization"] = None
        return cleaned
    
    def save(self, commit=True):
        user = super().save(commit=False)

        # enforce mapping on save too
        if user.role == "DOCTOR" and user.specialization:
            user.department = user.specialization.department
        else:
            user.specialization = None

        if commit:
            user.save()
        return user
   
class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['full_name', 'phone_number', 'email', 'address', 'gender', 'dob']

class AssignDoctorForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ["assigned_doctor"]

class AdmissionForm(forms.ModelForm):
    class Meta:
        model = Admission
        fields = ['ward', 'bed', 'reason', 'notes']

        def clean_bed(self):
            bed = self.cleaned_data.get("bed")
            if bed and bed.status != Bed.Status.AVAILABLE:
                raise forms.ValidationError("Selected bed is not available.")
            return bed

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            'patient',
            'doctor',
            'appointment_date',
            'appointment_time',
            'reason',
            'notes',
        ]
        
        widgets = {
            "appointment_date": forms.DateInput(attrs={"type": "date"}),
            "appointment_time": forms.TimeInput(attrs={"type": "time"}),
        }
    def clean(self):
        cleaned = super().clean()
        doctor = cleaned.get("doctor")
        date = cleaned.get("appointment_date")
        time = cleaned.get("appointment_time")

        if doctor and date and time:
            exists = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=date,
                appointment_time=time,
                status="SCHEDULED"
            ).exists()

            if exists:
                raise forms.ValidationError("An appointment already exists for this doctor at the selected time.")
        return cleaned
    
class EMRForm(forms.ModelForm):
    class Meta:
        model = EMR
        fields = ["diagnosis", "symptoms", "prescription", "notes"]

class VitalsForm(forms.ModelForm):
    class Meta:
        model = Vitals
        fields = ["bp_systolic", "bp_diastolic", "temperature_c", "pulse", "spo2", "weight_kg"]

PrescriptionFormSet = inlineformset_factory(
    EMR,
    PrescriptionItem,
    fields= ["medicine_name", "strength", "form", "dose", "frequency", "duration", "instructions"],
    extra=1,
    can_delete=True,
)

class LabOrderForm(forms.ModelForm):
    class Meta:
        model = LabOrder
        fields = ["notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

class LabOrderItemForm(forms.ModelForm):
    class Meta:
        model = LabOrderItem
        fields = ["test_type"]

LabOrderItemFormSet = inlineformset_factory(
    LabOrder,
    LabOrderItem,
    form=LabOrderItemForm,
    extra=1,
    can_delete=True,
)

class LabResultItemForm(forms.ModelForm):
    class Meta:
        model = LabOrderItem
        fields = ["result_value", "result_note", "is_abnormal"]

LabResultFormSet = inlineformset_factory(
    LabOrder,
    LabOrderItem,
    form=LabResultItemForm,
    extra=0,
    can_delete=False,
)

class LabTestTypeForm(forms.ModelForm):
    class Meta:
        model = LabTestType
        fields = ["name", "department", "normal_range", "unit", "price"]
        widgets = {
            "normal_range": forms.TextInput(attrs={"placeholder": "e.g. 3.5-5.5 or  >= 10 or  <= 200"}),
        }