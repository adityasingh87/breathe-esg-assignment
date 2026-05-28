from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (IngestionJobViewSet, EmissionRecordViewSet, UnitLookupViewSet, 
                    EmissionFactorViewSet, IngestView, BulkApproveView, 
                    AnalyticsSummaryView, AnalyticsReviewQueueView)

router = DefaultRouter()
router.register(r'jobs', IngestionJobViewSet, basename='job')
router.register(r'records', EmissionRecordViewSet, basename='record')
router.register(r'units', UnitLookupViewSet)
router.register(r'emission-factors', EmissionFactorViewSet)

urlpatterns = [
    path('v1/records/bulk-approve/', BulkApproveView.as_view(), name='bulk-approve'),
    path('v1/', include(router.urls)),
    path('v1/ingest/<str:source_type>/', IngestView.as_view(), name='ingest'),
    path('v1/summary/', AnalyticsSummaryView.as_view(), name='summary'),
    path('v1/summary/review-queue/', AnalyticsReviewQueueView.as_view(), name='review-queue'),
]
