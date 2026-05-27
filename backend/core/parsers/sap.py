import csv
import json
import datetime
from decimal import Decimal, InvalidOperation
from .base import BaseParser
from core.utils.reference_data import HEADER_ALIASES, SAP_PLANTS
from core.models import EmissionRecord, IngestionJob

class SAPParser(BaseParser):
    def parse_file(self, file_stream):
        reader = csv.reader(file_stream)
        
        try:
            headers = next(reader)
        except StopIteration:
            return  # Empty file

        mapping = self.standardize_headers(headers, HEADER_ALIASES['sap'])
        
        # Check required columns
        required_keys = ['plant', 'material_group', 'quantity', 'unit', 'date']
        missing_keys = [k for k in required_keys if k not in mapping]
        if missing_keys:
            self.add_error(1, ",".join(headers), "MISSING_HEADERS", f"Missing required headers: {missing_keys}")
            return

        for row_idx, row in enumerate(reader, start=2):
            # Skip empty rows
            if not any(row):
                continue
            
            raw_row_str = ",".join(row)
            
            def get_val(key):
                idx = mapping.get(key)
                if idx is not None and idx < len(row):
                    return row[idx].strip()
                return ""
            
            plant_code = get_val('plant')
            material_group = get_val('material_group')
            quantity_str = get_val('quantity')
            unit_str = get_val('unit')
            date_str = get_val('date')
            description = get_val('description')

            # Build raw_payload
            raw_payload = {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}

            # 1. Parse Date (YYYYMMDD or DD.MM.YYYY)
            if not date_str:
                self.add_error(row_idx, raw_row_str, "MISSING_DATE", "Date column is empty")
                continue
                
            activity_date = None
            for fmt in ('%Y%m%d', '%d.%m.%Y', '%Y-%m-%d'):
                try:
                    activity_date = datetime.datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue
            
            if not activity_date:
                self.add_error(row_idx, raw_row_str, "INVALID_DATE", f"Cannot parse date: {date_str}")
                continue

            # 2. Plant -> Region
            plant_info = SAP_PLANTS.get(plant_code)
            if not plant_info:
                self.add_error(row_idx, raw_row_str, "UNKNOWN_PLANT", f"Plant code not in reference table: {plant_code}")
                continue
            region = plant_info['region']

            # 3. Quantity
            try:
                # SAP often uses comma as decimal in German locales, or point in English
                quantity = Decimal(quantity_str.replace(',', '.'))
                if quantity <= 0:
                    self.add_error(row_idx, raw_row_str, "NEGATIVE_QUANTITY", f"Quantity is zero or negative: {quantity}")
                    continue
            except InvalidOperation:
                self.add_error(row_idx, raw_row_str, "INVALID_QUANTITY", f"Cannot parse quantity: {quantity_str}")
                continue

            # 4. Scope & Category Assignment
            mg_lower = material_group.lower()
            if 'diesel' in mg_lower or 'petrol' in mg_lower or 'fuel' in mg_lower:
                scope = 'scope_1'
                source_type = 'fuel'
                # fallback category from material_group if it maps, else use it as is
                category = 'diesel' if 'diesel' in mg_lower else ('petrol' if 'petrol' in mg_lower else 'fuel_combustion')
            else:
                scope = 'scope_2'
                source_type = 'electricity'
                category = 'grid_electricity'

            # 5. Unit Normalization
            unit_obj = self.units.get(unit_str.lower())
            if not unit_obj:
                self.add_error(row_idx, raw_row_str, "UNKNOWN_UNIT", f"Unit not found in unit lookup: {unit_str}")
                continue

            base_qty = quantity * unit_obj.factor_to_base
            base_unit = unit_obj.base_unit

            # 6. Emission Factor
            factor_obj = self._find_factor(source_type, category, region)
            
            normalized_kg = None
            if factor_obj:
                normalized_kg = base_qty * factor_obj.kg_co2e_per_unit

            # Append Record
            record = EmissionRecord(
                tenant=self.tenant,
                job=self.job,
                scope=scope,
                category=category,
                source_type=self.job.source_type, # 'sap'
                activity_date=activity_date,
                raw_quantity=quantity,
                raw_unit=unit_str,
                description=description,
                normalized_quantity_kg=normalized_kg,
                unit_lookup=unit_obj,
                emission_factor=factor_obj,
                raw_payload=raw_payload,
                source_row_number=row_idx,
                review_status=EmissionRecord.ReviewStatus.PENDING
            )
            self.records.append(record)
