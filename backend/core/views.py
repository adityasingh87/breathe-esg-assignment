from rest_framework import viewsets, views, status, parsers
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Count, Sum
from django.utils import timezone
from .models import IngestionJob, EmissionRecord, IngestionError, AuditLog, UnitLookup, EmissionFactor
from .serializers import (IngestionJobSerializer, EmissionRecordSerializer, IngestionErrorSerializer, 
                          AuditLogSerializer, UnitLookupSerializer, EmissionFactorSerializer)
from .tasks import process_ingestion_job
import json, uuid
from decimal import Decimal

def json_safe(data):
    """Recursively convert UUID/Decimal values to JSON-serializable types."""
    if isinstance(data, dict):
        return {k: json_safe(v) for k, v in data.items()}
    if isinstance(data, list):
        return [json_safe(v) for v in data]
    if isinstance(data, uuid.UUID):
        return str(data)
    if isinstance(data, Decimal):
        return float(data)
    return data

class IngestionJobViewSet(viewsets.ModelViewSet):
    serializer_class = IngestionJobSerializer
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    def get_queryset(self):
        return IngestionJob.objects.filter(tenant=self.request.tenant)

    @action(detail=True, methods=['get'])
    def errors(self, request, pk=None):
        job = self.get_object()
        errors = IngestionError.objects.filter(job=job)
        page = self.paginate_queryset(errors)
        if page is not None:
            serializer = IngestionErrorSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = IngestionErrorSerializer(errors, many=True)
        return Response(serializer.data)

class IngestView(views.APIView):
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    def post(self, request, source_type, *args, **kwargs):
        if source_type not in ['sap', 'utility', 'travel']:
            return Response({"error": "Invalid source type"}, status=status.HTTP_400_BAD_REQUEST)
        
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        job = IngestionJob.objects.create(
            tenant=request.tenant,
            source_type=source_type,
            file_name=file_obj.name,
            file=file_obj,
            ingested_by=request.user.email if request.user.email else request.user.username
        )

        process_ingestion_job.delay(job.id)

        return Response({
            "job_id": job.id,
            "status": job.status,
            "file_name": job.file_name
        }, status=status.HTTP_201_CREATED)

class EmissionRecordViewSet(viewsets.ModelViewSet):
    serializer_class = EmissionRecordSerializer

    def get_queryset(self):
        queryset = EmissionRecord.objects.filter(tenant=self.request.tenant)
        # Filters
        for field in ['scope', 'source_type', 'review_status', 'job_id']:
            val = self.request.query_params.get(field)
            if val:
                queryset = queryset.filter(**{field: val})
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(activity_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(activity_date__lte=date_to)
        return queryset

    def perform_update(self, serializer):
        record = self.get_object()
        if record.review_status == EmissionRecord.ReviewStatus.LOCKED:
            raise serializers.ValidationError("Cannot edit a locked record.")
        
        before_state = json_safe(EmissionRecordSerializer(record).data)
        serializer.save(is_edited=True)
        record.refresh_from_db()
        after_state = json_safe(EmissionRecordSerializer(record).data)

        AuditLog.objects.create(
            record=record,
            changed_by=self.request.user.email or self.request.user.username,
            action='edited',
            before_state=before_state,
            after_state=after_state
        )
        
        # We would also trigger re-normalization here, but for prototype we just log the edit

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        record = self.get_object()
        if record.review_status == EmissionRecord.ReviewStatus.LOCKED:
            return Response({"error": "Record is locked"}, status=status.HTTP_403_FORBIDDEN)
        
        before_state = json_safe(EmissionRecordSerializer(record).data)
        record.review_status = EmissionRecord.ReviewStatus.APPROVED
        record.reviewed_by = request.user.email or request.user.username
        record.reviewed_at = timezone.now()
        record.save()
        after_state = json_safe(EmissionRecordSerializer(record).data)
        
        AuditLog.objects.create(
            record=record,
            changed_by=request.user.email or request.user.username,
            action='approved',
            before_state=before_state,
            after_state=after_state
        )
        return Response({"status": "approved"})

    @action(detail=True, methods=['post'])
    def flag(self, request, pk=None):
        record = self.get_object()
        if record.review_status == EmissionRecord.ReviewStatus.LOCKED:
            return Response({"error": "Record is locked"}, status=status.HTTP_403_FORBIDDEN)
            
        reason = request.data.get('reason', '')
        before_state = json_safe(EmissionRecordSerializer(record).data)
        record.review_status = EmissionRecord.ReviewStatus.FLAGGED
        record.flag_reason = reason
        record.save()
        after_state = json_safe(EmissionRecordSerializer(record).data)
        
        AuditLog.objects.create(
            record=record,
            changed_by=request.user.email or request.user.username,
            action='flagged',
            before_state=before_state,
            after_state=after_state
        )
        return Response({"status": "flagged"})

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        record = self.get_object()
        if record.review_status != EmissionRecord.ReviewStatus.APPROVED:
            return Response({"error": "Only approved records can be locked"}, status=status.HTTP_400_BAD_REQUEST)
            
        before_state = json_safe(EmissionRecordSerializer(record).data)
        record.review_status = EmissionRecord.ReviewStatus.LOCKED
        record.locked_by = request.user.email or request.user.username
        record.locked_at = timezone.now()
        record.save()
        after_state = json_safe(EmissionRecordSerializer(record).data)
        
        AuditLog.objects.create(
            record=record,
            changed_by=request.user.email or request.user.username,
            action='locked',
            before_state=before_state,
            after_state=after_state
        )
        return Response({"status": "locked"})

    @action(detail=True, methods=['get'])
    def audit(self, request, pk=None):
        record = self.get_object()
        logs = AuditLog.objects.filter(record=record).order_by('changed_at')
        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data)

class BulkApproveView(views.APIView):
    def post(self, request):
        ids = request.data.get('ids', [])
        records = EmissionRecord.objects.filter(id__in=ids, tenant=request.tenant).exclude(review_status=EmissionRecord.ReviewStatus.LOCKED)
        count = 0
        user_identifier = request.user.email or request.user.username
        for record in records:
            before_state = json_safe(EmissionRecordSerializer(record).data)
            record.review_status = EmissionRecord.ReviewStatus.APPROVED
            record.reviewed_by = user_identifier
            record.reviewed_at = timezone.now()
            record.save()
            after_state = json_safe(EmissionRecordSerializer(record).data)
            AuditLog.objects.create(
                record=record,
                changed_by=user_identifier,
                action='approved',
                before_state=before_state,
                after_state=after_state
            )
            count += 1
        return Response({"approved_count": count})

class AnalyticsSummaryView(views.APIView):
    def get(self, request):
        queryset = EmissionRecord.objects.filter(tenant=request.tenant)
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(activity_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(activity_date__lte=date_to)

        summary_by_scope = queryset.values('scope').annotate(total=Sum('normalized_quantity_kg'))
        summary_by_source = queryset.values('source_type').annotate(total=Sum('normalized_quantity_kg'))
        
        return Response({
            "by_scope": {item['scope']: item['total'] for item in summary_by_scope if item['scope']},
            "by_source": {item['source_type']: item['total'] for item in summary_by_source if item['source_type']}
        })

class AnalyticsReviewQueueView(views.APIView):
    def get(self, request):
        queryset = EmissionRecord.objects.filter(tenant=request.tenant)
        summary = queryset.values('source_type', 'review_status').annotate(count=Count('id'))
        
        result = {'sap': {}, 'utility': {}, 'travel': {}}
        for s in result.keys():
            for stat in ['pending', 'approved', 'flagged', 'locked']:
                result[s][stat] = 0
                
        for item in summary:
            if item['source_type'] in result:
                result[item['source_type']][item['review_status']] = item['count']
                
        return Response(result)

class UnitLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UnitLookup.objects.all()
    serializer_class = UnitLookupSerializer

class EmissionFactorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EmissionFactor.objects.all()
    serializer_class = EmissionFactorSerializer
    filterset_fields = ['source_type', 'category', 'region', 'year']
