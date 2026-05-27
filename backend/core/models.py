"""
Breathe ESG — Core Models
Implements the full database schema from the Platform Design specification.
"""

import uuid
from django.db import models


class Tenant(models.Model):
    """Represents a client organisation. All data is scoped to a tenant."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True, help_text="URL-safe identifier, e.g. acme-corp")
    timezone = models.CharField(max_length=50, default='UTC')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UnitLookup(models.Model):
    """Reference table for unit normalisation.
    Raw units → base unit (kWh / km / kg) via factor_to_base."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_unit = models.CharField(max_length=30, unique=True, help_text="e.g. kWh, litres, MWh")
    factor_to_base = models.DecimalField(max_digits=18, decimal_places=10,
                                         help_text="Multiplier to convert to base unit")
    base_unit = models.CharField(max_length=20, help_text="kWh for energy, km for distance, kg for mass")
    notes = models.TextField(blank=True, default='')

    def __str__(self):
        return f"{self.from_unit} → {self.base_unit} (×{self.factor_to_base})"


class EmissionFactor(models.Model):
    """Stores emission factors used at calculation time.
    FK'd from EmissionRecord so auditors can see which factor was applied."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_type = models.CharField(max_length=20, help_text="electricity | fuel | travel_air | travel_hotel | travel_ground")
    category = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True, default='',
                              help_text="IN, GB, US-CA, etc.")
    kg_co2e_per_unit = models.DecimalField(max_digits=18, decimal_places=10)
    unit = models.CharField(max_length=30, help_text="The base unit this factor applies to")
    year = models.IntegerField()
    source_ref = models.CharField(max_length=255, blank=True, default='',
                                  help_text="e.g. DEFRA 2023, IEA 2023")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['source_type', 'category', 'region', 'year']),
        ]

    def __str__(self):
        return f"{self.category} ({self.region}) — {self.kg_co2e_per_unit} kg CO₂e/{self.unit}"


class IngestionJob(models.Model):
    """One row per file upload. Tracks the lifecycle of an ingestion run."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        DONE = 'done', 'Done'
        FAILED = 'failed', 'Failed'

    class SourceType(models.TextChoices):
        SAP = 'sap', 'SAP'
        UTILITY = 'utility', 'Utility'
        TRAVEL = 'travel', 'Travel'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='jobs')
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    file_name = models.CharField(max_length=500)
    file_hash = models.CharField(max_length=64, blank=True, default='',
                                 help_text="SHA-256 for dedup detection")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    total_rows = models.IntegerField(null=True, blank=True)
    parsed_rows = models.IntegerField(null=True, blank=True)
    error_rows = models.IntegerField(null=True, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    ingested_by = models.CharField(max_length=255, help_text="Email of uploader")
    # Store the uploaded file
    file = models.FileField(upload_to='ingestion_files/', blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'source_type']),
            models.Index(fields=['tenant', 'status']),
        ]

    def __str__(self):
        return f"{self.source_type} — {self.file_name} ({self.status})"


class EmissionRecord(models.Model):
    """Central table. One row per normalised activity data point."""

    class ReviewStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        FLAGGED = 'flagged', 'Flagged'
        LOCKED = 'locked', 'Locked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='records')
    job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name='records')

    # Scope & classification
    scope = models.CharField(max_length=10, help_text="scope_1 | scope_2 | scope_3")
    category = models.CharField(max_length=100, help_text="e.g. fuel_combustion, business_travel_air")
    source_type = models.CharField(max_length=20)

    # Activity data (as received, before normalisation)
    activity_date = models.DateField()
    raw_quantity = models.DecimalField(max_digits=18, decimal_places=6)
    raw_unit = models.CharField(max_length=30, help_text="e.g. litres, kWh, km")
    description = models.TextField(blank=True, default='')

    # Normalised output
    normalized_quantity_kg = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True,
                                                  help_text="kg CO₂e")
    unit_lookup = models.ForeignKey(UnitLookup, on_delete=models.SET_NULL, null=True, blank=True)
    emission_factor = models.ForeignKey(EmissionFactor, on_delete=models.SET_NULL, null=True, blank=True)

    # Source of truth tracking
    raw_payload = models.JSONField(help_text="Verbatim source row as JSON")
    source_row_number = models.IntegerField(null=True, blank=True)

    # Review workflow
    review_status = models.CharField(max_length=20, choices=ReviewStatus.choices,
                                     default=ReviewStatus.PENDING)
    flag_reason = models.TextField(blank=True, default='')
    reviewed_by = models.CharField(max_length=255, blank=True, default='')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.CharField(max_length=255, blank=True, default='')
    locked_at = models.DateTimeField(null=True, blank=True)
    is_edited = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'review_status']),
            models.Index(fields=['tenant', 'scope', 'activity_date']),
            models.Index(fields=['job']),
        ]

    def __str__(self):
        return f"{self.scope}/{self.category} — {self.raw_quantity} {self.raw_unit} ({self.activity_date})"


class IngestionError(models.Model):
    """Per-row errors from a failed or partially failed ingestion job."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name='errors')
    row_number = models.IntegerField()
    raw_row = models.TextField(blank=True, default='', help_text="Original CSV row as string")
    error_code = models.CharField(max_length=50, help_text="e.g. MISSING_DATE, UNKNOWN_UNIT")
    error_message = models.TextField()

    class Meta:
        indexes = [
            models.Index(fields=['job']),
        ]

    def __str__(self):
        return f"Row {self.row_number}: {self.error_code}"


class AuditLog(models.Model):
    """Append-only. One row per change to an emission record."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_logs')
    changed_by = models.CharField(max_length=255)
    action = models.CharField(max_length=30,
                              help_text="created | edited | approved | flagged | locked")
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField()
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['record', 'changed_at']),
        ]
        ordering = ['changed_at']

    def __str__(self):
        return f"{self.action} by {self.changed_by} @ {self.changed_at}"
