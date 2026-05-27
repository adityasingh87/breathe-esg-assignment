from rest_framework import serializers
from .models import Tenant, IngestionJob, EmissionRecord, IngestionError, AuditLog, UnitLookup, EmissionFactor

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = '__all__'

class IngestionJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionJob
        fields = '__all__'
        read_only_fields = ['id', 'tenant', 'status', 'total_rows', 'parsed_rows', 'error_rows', 'ingested_at', 'file_hash']

class IngestionErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionError
        fields = '__all__'

class EmissionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionRecord
        fields = '__all__'
        read_only_fields = ['id', 'tenant', 'job', 'scope', 'category', 'source_type', 'normalized_quantity_kg', 
                            'unit_lookup', 'emission_factor', 'raw_payload', 'source_row_number', 'review_status', 
                            'reviewed_by', 'reviewed_at', 'locked_by', 'locked_at', 'is_edited']

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = '__all__'

class UnitLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitLookup
        fields = '__all__'

class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactor
        fields = '__all__'
