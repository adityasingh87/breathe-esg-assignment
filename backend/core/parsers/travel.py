import csv
import datetime
from decimal import Decimal, InvalidOperation
from .base import BaseParser
from core.utils.reference_data import HEADER_ALIASES, IATA_DISTANCES_KM
from core.models import EmissionRecord

class TravelParser(BaseParser):
    def parse_file(self, file_stream):
        reader = csv.reader(file_stream)

        try:
            headers = next(reader)
        except StopIteration:
            return

        mapping = self.standardize_headers(headers, HEADER_ALIASES['travel'])

        # Only 'date' is universally required; type-specific fields are validated per row
        if 'date' not in mapping:
            self.add_error(1, ",".join(headers), "MISSING_HEADERS", "Missing required header: Date")
            return

        for row_idx, row in enumerate(reader, start=2):
            if not any(cell.strip() for cell in row):
                continue

            raw_row_str = ",".join(row)

            def get_val(key):
                idx = mapping.get(key)
                if idx is not None and idx < len(row):
                    return row[idx].strip()
                return ""

            # Common fields
            date_str = get_val('date')
            travel_type = get_val('travel_type').lower()  # 'air', 'hotel', 'ground'
            employee_id = get_val('employee_id')

            raw_payload = {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}

            # Date parsing
            activity_date = None
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y%m%d'):
                try:
                    activity_date = datetime.datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue

            if not activity_date:
                self.add_error(row_idx, raw_row_str, "MISSING_DATE", f"Cannot parse date: {date_str}")
                continue

            # ── Hotel travel ──────────────────────────────────────────────────────────
            if travel_type == 'hotel':
                nights_str = get_val('hotel_nights')
                try:
                    nights = Decimal(nights_str)
                    if nights <= 0:
                        raise ValueError("Non-positive nights")
                except (InvalidOperation, ValueError):
                    self.add_error(row_idx, raw_row_str, "INVALID_HOTEL_NIGHTS",
                                   f"Cannot parse hotel nights: '{nights_str}'")
                    continue

                factor_obj = self._find_factor('travel_hotel', 'hotel_stay', 'global')
                normalized_kg = float(nights) * float(factor_obj.kg_co2e_per_unit) if factor_obj else None

                self.records.append(EmissionRecord(
                    tenant=self.tenant,
                    job=self.job,
                    scope='scope_3',
                    category='hotel_stay',
                    source_type=self.job.source_type,
                    activity_date=activity_date,
                    raw_quantity=nights,
                    raw_unit='nights',
                    description=f"Hotel stay by {employee_id} for {nights} nights",
                    normalized_quantity_kg=normalized_kg,
                    unit_lookup=None,
                    emission_factor=factor_obj,
                    raw_payload=raw_payload,
                    source_row_number=row_idx,
                    review_status=EmissionRecord.ReviewStatus.PENDING
                ))
                continue

            # ── Ground travel ─────────────────────────────────────────────────────────
            if travel_type == 'ground':
                distance_str = get_val('distance')
                unit_str = get_val('unit').lower() or 'km'

                try:
                    distance = Decimal(distance_str)
                    if distance <= 0:
                        raise ValueError("Non-positive distance")
                except (InvalidOperation, ValueError):
                    self.add_error(row_idx, raw_row_str, "INVALID_DISTANCE",
                                   f"Cannot parse distance: '{distance_str}'")
                    continue

                unit_obj = self.units.get(unit_str)
                if not unit_obj:
                    self.add_error(row_idx, raw_row_str, "UNKNOWN_UNIT",
                                   f"Unknown unit: '{unit_str}'")
                    continue

                base_qty = distance * unit_obj.factor_to_base  # convert to km
                factor_obj = self._find_factor('travel_ground', 'car', 'global')
                normalized_kg = float(base_qty) * float(factor_obj.kg_co2e_per_unit) if factor_obj else None

                self.records.append(EmissionRecord(
                    tenant=self.tenant,
                    job=self.job,
                    scope='scope_3',
                    category='car',
                    source_type=self.job.source_type,
                    activity_date=activity_date,
                    raw_quantity=distance,
                    raw_unit=unit_str,
                    description=f"Ground travel by {employee_id}: {distance} {unit_str}",
                    normalized_quantity_kg=normalized_kg,
                    unit_lookup=unit_obj,
                    emission_factor=factor_obj,
                    raw_payload=raw_payload,
                    source_row_number=row_idx,
                    review_status=EmissionRecord.ReviewStatus.PENDING
                ))
                continue

            # ── Air travel (default) ──────────────────────────────────────────────────
            origin = get_val('origin').upper()
            destination = get_val('destination').upper()
            flight_class = get_val('class').lower()

            # Try IATA lookup first, then manual distance
            distance_km = IATA_DISTANCES_KM.get((origin, destination))
            if distance_km is None:
                distance_str = get_val('distance')
                unit_str = get_val('unit').lower() or 'km'
                if distance_str:
                    try:
                        manual_dist = Decimal(distance_str)
                        unit_obj = self.units.get(unit_str)
                        if unit_obj:
                            distance_km = float(manual_dist * unit_obj.factor_to_base)
                    except (InvalidOperation, ValueError):
                        pass

            if distance_km is None:
                if not origin and not destination:
                    self.add_error(row_idx, raw_row_str, "MISSING_FLIGHT_DATA",
                                   "Air row missing origin, destination, and distance")
                else:
                    self.add_error(row_idx, raw_row_str, "UNKNOWN_AIRPORT_PAIR",
                                   f"Unresolvable airport pair: {origin} -> {destination}")
                continue

            # Class multiplier
            multiplier = Decimal('1.0')
            if 'business' in flight_class:
                multiplier = Decimal('1.5')
                category = 'business_flight'
            elif 'first' in flight_class:
                multiplier = Decimal('2.0')
                category = 'first_class_flight'
            else:
                category = 'economy_flight'

            base_qty = Decimal(str(distance_km)) * multiplier
            unit_obj = self.units.get('km')
            factor_obj = self._find_factor('travel_air', category, 'global') or \
                         self._find_factor('travel_air', 'economy_flight', 'global')
            normalized_kg = float(base_qty) * float(factor_obj.kg_co2e_per_unit) if factor_obj else None

            self.records.append(EmissionRecord(
                tenant=self.tenant,
                job=self.job,
                scope='scope_3',
                category=category,
                source_type=self.job.source_type,
                activity_date=activity_date,
                raw_quantity=base_qty,
                raw_unit='km',
                description=f"Flight {origin} to {destination} ({flight_class}) by {employee_id}",
                normalized_quantity_kg=normalized_kg,
                unit_lookup=unit_obj,
                emission_factor=factor_obj,
                raw_payload=raw_payload,
                source_row_number=row_idx,
                review_status=EmissionRecord.ReviewStatus.PENDING
            ))
