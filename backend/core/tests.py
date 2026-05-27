from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from core.models import Tenant, UnitLookup, EmissionFactor, IngestionJob, EmissionRecord
import datetime
from decimal import Decimal
from core.parsers.sap import SAPParser
from django.core.files.uploadedfile import SimpleUploadedFile

class APITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.tenant = Tenant.objects.create(name='Test Tenant', slug='test-tenant')
        
        # We need a JWT token
        response = self.client.post('/api/auth/token/', {'username': 'testuser', 'password': 'testpassword'}, format='json')
        self.token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)

    def test_get_records(self):
        # Without auth, should be 401
        self.client.credentials()
        response = self.client.get('/api/v1/records/')
        self.assertEqual(response.status_code, 401)
        
        # With auth, should be 200
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        response = self.client.get('/api/v1/records/')
        self.assertEqual(response.status_code, 200)

class ParserTestCase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test Tenant', slug='test-tenant')
        
        # Need basic units and factors for the parser to not fail completely
        UnitLookup.objects.create(from_unit='L', base_unit='litres', factor_to_base=Decimal('1.0'))
        EmissionFactor.objects.create(
            source_type='fuel', category='diesel', region='global', 
            year=2024, unit='litres', kg_co2e_per_unit=Decimal('2.68')
        )
        
        self.job = IngestionJob.objects.create(
            tenant=self.tenant,
            source_type='sap',
            file_name='test.csv',
            ingested_by='test'
        )

    def test_sap_parser(self):
        csv_content = b"Plant,Material Group,Quantity,Unit,Posting Date,Material Description\nDE01,Diesel,100,L,20240101,Fuel for generator\n"
        from io import StringIO
        # create file stream
        f = StringIO(csv_content.decode('utf-8'))
        
        parser = SAPParser(self.job)
        parser.parse_file(f)
        
        self.assertEqual(len(parser.errors), 0)
        self.assertEqual(len(parser.records), 1)
        
        record = parser.records[0]
        self.assertEqual(record.scope, 'scope_1')
        self.assertEqual(record.raw_quantity, Decimal('100'))
