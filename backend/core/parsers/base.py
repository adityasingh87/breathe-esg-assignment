import csv
import io
from typing import Dict, List, Tuple
from core.models import Tenant, IngestionJob, EmissionRecord, IngestionError, UnitLookup, EmissionFactor

class BaseParser:
    """Base class for all file parsers."""

    def __init__(self, job: IngestionJob):
        self.job = job
        self.tenant = job.tenant
        self.errors = []
        self.records = []
        
        # Load lookups into memory for fast processing
        self._load_lookups()

    def _load_lookups(self):
        self.units = {u.from_unit.lower(): u for u in UnitLookup.objects.all()}
        # For emission factors, it's better to query them as needed or load into a structured dict
        self.factors = list(EmissionFactor.objects.all())

    def _find_factor(self, source_type, category, region='global'):
        # Fallback logic: specific region -> 'global'
        for f in self.factors:
            if f.source_type == source_type and f.category == category and f.region == region:
                return f
        for f in self.factors:
            if f.source_type == source_type and f.category == category and f.region == 'global':
                return f
        return None

    def add_error(self, row_number: int, raw_row: str, code: str, message: str):
        self.errors.append(
            IngestionError(
                job=self.job,
                row_number=row_number,
                raw_row=raw_row,
                error_code=code,
                error_message=message
            )
        )

    def standardize_headers(self, headers: List[str], aliases: Dict[str, List[str]]) -> Dict[str, int]:
        """Maps file headers to standard internal keys using an alias dict."""
        mapping = {}
        for col_idx, header in enumerate(headers):
            header_clean = header.strip().lower()
            for key, alias_list in aliases.items():
                if header_clean in [a.lower() for a in alias_list]:
                    mapping[key] = col_idx
                    break
        return mapping

    def parse_file(self, file_stream):
        """Main entry point. To be implemented by subclasses."""
        raise NotImplementedError()

    def save(self):
        """Bulk creates parsed records and errors."""
        # Save records
        if self.records:
            EmissionRecord.objects.bulk_create(self.records)
        
        # Save errors
        if self.errors:
            IngestionError.objects.bulk_create(self.errors)
        
        self.job.total_rows = len(self.records) + len(self.errors)
        self.job.parsed_rows = len(self.records)
        self.job.error_rows = len(self.errors)
        self.job.status = IngestionJob.Status.DONE if not self.errors else IngestionJob.Status.FAILED
        # We can also consider a PARTIAL status if some rows succeeded and some failed, 
        # but PLATFORM_DESIGN only specifies pending | processing | done | failed.
        # Actually, let's use DONE if at least one record succeeded, or FAILED if all failed.
        # Wait, if there are errors, should we still save the valid records? Yes.
        if self.errors and len(self.records) == 0:
            self.job.status = IngestionJob.Status.FAILED
        elif self.errors:
            # According to PLATFORM_DESIGN, failed or partially failed jobs have errors.
            # I will mark it as DONE if there are some parsed rows, maybe we just leave it to the task to decide.
            # Let's say if errors exist but some parsed, it's DONE but with error_rows > 0.
            pass

        self.job.save()

