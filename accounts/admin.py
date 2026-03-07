from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Bed, Department, Patient, Admission, Ward, Specialization, LabTestType, LabOrder, LabOrderItem, WardTariff, DoctorVisit, NursingCharge, Medicine, MedicineUsage

User = get_user_model()
# Register your models here.
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'full_name', 'role', 'department', 'specialization', 'is_active']
    search_fields = ['username', 'full_name', 'email']
    list_filter = ['role', 'department', 'is_active']

admin.site.register(Department) 
admin.site.register(Patient)
admin.site.register(Admission)
admin.site.register(Ward)
admin.site.register(Bed)
admin.site.register(Specialization)
admin.site.register(DoctorVisit)
admin.site.register(NursingCharge)
admin.site.register(Medicine)
admin.site.register(MedicineUsage)

@admin.register(LabTestType)
class LabTestTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "normal_range", "unit", "price")
    list_filter = ("department",)
    search_fields = ("name",)
    ordering = ("name",)

class LabOrderItemInline(admin.TabularInline):
    model = LabOrderItem
    extra = 0
    fields = ("test_type", "result_value", "result_note", "is_abnormal")
    readonly_fields = ("is_abnormal",)
    

@admin.register(LabOrder)
class LabOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "status", "requested_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("patient__patient_id", "patient__full_name")
    ordering = ("-created_at",)
    inlines = [LabOrderItemInline]

@admin.register(WardTariff)
class WardTariffAmdin(admin.ModelAdmin):
    list_display = ("ward", "bed_charge_per_day", "icu_extra_per_day", "ventilator_extra_per_day")