from django.contrib import admin

from .models import CertificateIssued, CertificateTemplate, CertProgram, OfflineConfirmation, XapiStatement


@admin.register(OfflineConfirmation)
class OfflineConfirmationAdmin(admin.ModelAdmin):
    list_display = ('employee', 'target_type', 'target_id', 'method', 'confirmed_by', 'confirmed_at', 'tenant')
    list_filter = ('tenant', 'target_type', 'method')


@admin.register(XapiStatement)
class XapiStatementAdmin(admin.ModelAdmin):
    list_display = ('employee', 'verb', 'object_type', 'object_id', 'timestamp', 'tenant')
    list_filter = ('tenant', 'verb', 'object_type')


@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'active', 'tenant')
    list_filter = ('tenant', 'type', 'active')


@admin.register(CertProgram)
class CertProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'active', 'tenant')
    list_filter = ('tenant', 'type', 'active')


@admin.register(CertificateIssued)
class CertificateIssuedAdmin(admin.ModelAdmin):
    list_display = ('code', 'employee', 'ref_type', 'ref_id', 'issue_date', 'tenant')
    list_filter = ('tenant', 'ref_type')
