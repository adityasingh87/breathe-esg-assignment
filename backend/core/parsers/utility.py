import csv
import datetime
from decimal import Decimal, InvalidOperation
from .base import BaseParser
from core.utils.reference_data import HEADER_ALIASES
from core.models import EmissionRecord, IngestionJob

class UtilityParser(BaseParser):
    def parse_file(self, file_stream):
        reader = csv.reader(file_stream)
        
        try:
            headers = next(reader)
        except StopIteration:
            return

        mapping = self.standardize_headers(headers, HEADER_ALIASES['utility'])
        
        required_keys = ['meter_id', 'start_date', 'consumption', 'unit']
        missing_keys = [k for k in required_keys if k not in mapping]
        if missing_keys:
            self.add_error(1, ",".join(headers), "MISSING_HEADERS", f"Missing required headers: {missing_keys}")
            return

        # Keep track of seen meter periods to detect duplicates in the file
        seen_meter_periods = set()

        for row_idx, row in enumerate(reader, start=2):
            if not any(row):
                continue
            
            raw_row_str = ",".join(row)
            
            def get_val(key):
                idx = mapping.get(key)
                if idx is not None and idx < len(row):
                    return row[idx].strip()
                return ""
            
            meter_id = get_val('meter_id')
            start_date_str = get_val('start_date')
            end_date_str = get_val('end_date')
            consumption_str = get_val('consumption')
            unit_str = get_val('unit')

            raw_payload = {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}

            # Date parsing
            activity_date = None
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
                try:
                    activity_date = datetime.datetime.strptime(start_date_str, fmt).date()
                    break
                except ValueError:
                    continue
            
            if not activity_date:
                self.add_error(row_idx, raw_row_str, "MISSING_DATE", f"Cannot parse start date: {start_date_str}")
                continue

            # Duplicate meter period check in this file
            meter_period = (meter_id, activity_date)
            if meter_period in seen_meter_periods:
                self.add_error(row_idx, raw_row_str, "DUPLICATE_METER_PERIOD", f"Duplicate meter period in file: {meter_id} for {activity_date}")
                continue
            seen_meter_periods.add(meter_period)

            # Note: We should also check the DB for duplicate meter period, but doing it in DB involves querying.
            # A simpler way is to check against existing records in DB for this tenant and meter_id.
            # However, for performance, we can skip DB check or do it during save, but for prototype we just flag obvious duplicates in file.
            
            # Check DB for duplicate meter period (SQLite-safe: filter by date and source_type only)
            existing = EmissionRecord.objects.filter(
                tenant=self.tenant,
                source_type='utility',
                activity_date=activity_date
            )
            # Check if any of those existing records have the same meter_id in their raw_payload
            duplicate_in_db = any(
                str(r.raw_payload.get('MeterID', r.raw_payload.get('Meter Number', ''))) == meter_id
                for r in existing
            )
            if duplicate_in_db:
                self.add_error(row_idx, raw_row_str, "DUPLICATE_METER_PERIOD", f"Duplicate meter period exists in database: {meter_id} for {activity_date}")
                continue

            try:
                quantity = Decimal(consumption_str.replace(',', ''))
                if quantity <= 0:
                    self.add_error(row_idx, raw_row_str, "NEGATIVE_QUANTITY", f"Quantity is zero or negative: {quantity}")
                    continue
            except InvalidOperation:
                self.add_error(row_idx, raw_row_str, "INVALID_QUANTITY", f"Cannot parse quantity: {consumption_str}")
                continue

            unit_obj = self.units.get(unit_str.lower())
            if not unit_obj:
                self.add_error(row_idx, raw_row_str, "UNKNOWN_UNIT", f"Unit not found in unit lookup: {unit_str}")
                continue

            base_qty = quantity * unit_obj.factor_to_base
            base_unit = unit_obj.base_unit

            # Assume region global or derive from tenant? Defaulting to global for utility if not specified
            factor_obj = self._find_factor('electricity', 'grid_electricity', 'global')
            
            normalized_kg = None
            if factor_obj:
                normalized_kg = base_qty * factor_obj.kg_co2e_per_unit

            record = EmissionRecord(
                tenant=self.tenant,
                job=self.job,
                scope='scope_2',
                category='purchased_electricity',
                source_type=self.job.source_type, # 'utility'
                activity_date=activity_date,
                raw_quantity=quantity,
                raw_unit=unit_str,
                description=f"Meter {meter_id} from {start_date_str} to {end_date_str}",
                normalized_quantity_kg=normalized_kg,
                unit_lookup=unit_obj,
                emission_factor=factor_obj,
                raw_payload=raw_payload,
                source_row_number=row_idx,
                review_status=EmissionRecord.ReviewStatus.PENDING
            )
            self.records.append(record)
