# pyrefly: ignore [missing-import]
from django.core.management.base import BaseCommand
from core.models import Tenant, UnitLookup, EmissionFactor
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Seeds the database with initial reference data (Tenants, UnitLookup, EmissionFactors)'

    def handle(self, *args, **kwargs):
        # 1. Seed Tenant
        tenant, created = Tenant.objects.get_or_create(
            slug='acme-corp',
            defaults={
                'name': 'Acme Corporation',
                'timezone': 'UTC'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created Tenant: {tenant.name}"))
        else:
            self.stdout.write(f"Tenant already exists: {tenant.name}")

        # 1.5 Create Admin User
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin')
            self.stdout.write(self.style.SUCCESS("Created admin user (username: admin, password: admin)"))

        # 2. Seed Unit Lookup
        units = [
            {'from_unit': 'kWh', 'base_unit': 'kWh', 'factor_to_base': 1.0, 'notes': 'Electricity base unit'},
            {'from_unit': 'MWh', 'base_unit': 'kWh', 'factor_to_base': 1000.0, 'notes': 'Megawatt hours to kWh'},
            {'from_unit': 'litres', 'base_unit': 'litres', 'factor_to_base': 1.0, 'notes': 'Fuel base unit'},
            {'from_unit': 'gallons', 'base_unit': 'litres', 'factor_to_base': 3.78541, 'notes': 'US Gallons to litres'},
            {'from_unit': 'km', 'base_unit': 'km', 'factor_to_base': 1.0, 'notes': 'Distance base unit'},
            {'from_unit': 'miles', 'base_unit': 'km', 'factor_to_base': 1.60934, 'notes': 'Miles to km'},
            {'from_unit': 'kg', 'base_unit': 'kg', 'factor_to_base': 1.0, 'notes': 'Mass base unit'},
            {'from_unit': 'tonnes', 'base_unit': 'kg', 'factor_to_base': 1000.0, 'notes': 'Metric tonnes to kg'},
        ]

        for u in units:
            obj, created = UnitLookup.objects.get_or_create(
                from_unit=u['from_unit'],
                defaults={
                    'base_unit': u['base_unit'],
                    'factor_to_base': u['factor_to_base'],
                    'notes': u['notes']
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created UnitLookup: {u['from_unit']} -> {u['base_unit']}"))

        # 3. Seed Emission Factors
        factors = [
            {
                'source_type': 'electricity', 'category': 'grid_electricity', 'region': 'IN',
                'year': 2024, 'unit': 'kWh', 'kg_co2e_per_unit': 0.71, 'source_ref': 'CEA 2023'
            },
            {
                'source_type': 'electricity', 'category': 'grid_electricity', 'region': 'US-CA',
                'year': 2024, 'unit': 'kWh', 'kg_co2e_per_unit': 0.23, 'source_ref': 'EPA eGRID 2023'
            },
            {
                'source_type': 'electricity', 'category': 'grid_electricity', 'region': 'GB',
                'year': 2024, 'unit': 'kWh', 'kg_co2e_per_unit': 0.19, 'source_ref': 'DEFRA 2023'
            },
            {
                'source_type': 'fuel', 'category': 'diesel', 'region': 'global',
                'year': 2024, 'unit': 'litres', 'kg_co2e_per_unit': 2.68, 'source_ref': 'DEFRA 2023'
            },
            {
                'source_type': 'fuel', 'category': 'petrol', 'region': 'global',
                'year': 2024, 'unit': 'litres', 'kg_co2e_per_unit': 2.31, 'source_ref': 'DEFRA 2023'
            },
            {
                'source_type': 'travel_air', 'category': 'economy_flight', 'region': 'global',
                'year': 2024, 'unit': 'km', 'kg_co2e_per_unit': 0.15, 'source_ref': 'DEFRA 2023'
            },
            {
                'source_type': 'travel_air', 'category': 'business_flight', 'region': 'global',
                'year': 2024, 'unit': 'km', 'kg_co2e_per_unit': 0.45, 'source_ref': 'DEFRA 2023'
            },
        ]

        for f in factors:
            obj, created = EmissionFactor.objects.get_or_create(
                source_type=f['source_type'],
                category=f['category'],
                region=f['region'],
                year=f['year'],
                defaults={
                    'unit': f['unit'],
                    'kg_co2e_per_unit': f['kg_co2e_per_unit'],
                    'source_ref': f['source_ref']
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created EmissionFactor: {f['category']} ({f['region']})"))

        self.stdout.write(self.style.SUCCESS('Successfully seeded database.'))
