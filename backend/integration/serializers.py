from rest_framework import serializers

from .models import CertificateIssued, CertificateTemplate, CertProgram, XapiStatement


class CertificateTemplateSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = CertificateTemplate
        fields = [
            'id', 'type', 'type_display', 'name', 'template_pdf_url', 'fields_config', 'active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CertProgramSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    certificate_template_name = serializers.CharField(
        source='certificate_template.name', read_only=True, default='',
    )

    class Meta:
        model = CertProgram
        fields = [
            'id', 'name', 'type', 'type_display', 'rule_config', 'certificate_template',
            'certificate_template_name', 'active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CertificateIssuedSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source='employee.code', read_only=True, default='')
    employee_name = serializers.CharField(source='employee.name', read_only=True, default='')
    ref_type_display = serializers.CharField(source='get_ref_type_display', read_only=True)
    program_name = serializers.CharField(source='program.name', read_only=True, default='')

    class Meta:
        model = CertificateIssued
        fields = [
            'id', 'employee', 'employee_code', 'employee_name', 'template', 'program',
            'program_name', 'ref_type', 'ref_type_display', 'ref_id', 'issue_date', 'code',
            'pdf_url', 'issued_at',
        ]
        read_only_fields = fields


class XapiStatementSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source='employee.code', read_only=True, default='')
    employee_name = serializers.CharField(source='employee.name', read_only=True, default='')
    verb_display = serializers.CharField(source='get_verb_display', read_only=True)
    object_type_display = serializers.CharField(source='get_object_type_display', read_only=True)

    class Meta:
        model = XapiStatement
        fields = [
            'id', 'employee', 'employee_code', 'employee_name', 'verb', 'verb_display',
            'object_type', 'object_type_display', 'object_id', 'result_json', 'context_json',
            'timestamp',
        ]
        read_only_fields = fields
