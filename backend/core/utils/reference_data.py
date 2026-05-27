__all__ = ['IATA_DISTANCES_KM', 'SAP_PLANTS', 'HEADER_ALIASES']

# Static lookup for SAP plant codes to region
SAP_PLANTS = {
    'DE01': {'name': 'Berlin Manufacturing', 'country': 'Germany', 'region': 'GB'}, # Using GB as proxy for EU/Germany factor if needed, or 'global'
    'IN01': {'name': 'Mumbai Assembly', 'country': 'India', 'region': 'IN'},
    'US01': {'name': 'California Warehouse', 'country': 'USA', 'region': 'US-CA'},
}

# Static lookup for IATA great-circle distances in km
IATA_DISTANCES_KM = {
    ('LHR', 'JFK'): 5540,
    ('JFK', 'LHR'): 5540,
    ('BOM', 'DEL'): 1140,
    ('DEL', 'BOM'): 1140,
    ('SFO', 'JFK'): 4150,
    ('JFK', 'SFO'): 4150,
    ('LHR', 'BOM'): 7190,
    ('BOM', 'LHR'): 7190,
}

# Mapping foreign language/alternative headers to standard English keys
HEADER_ALIASES = {
    'sap': {
        'plant': ['Plant', 'Werk', 'PlantCode'],
        'material_group': ['Material Group', 'Warengruppe', 'MaterialGroup'],
        'quantity': ['Quantity', 'Menge', 'Amount'],
        'unit': ['Unit', 'Basiseinheit', 'UOM'],
        'date': ['Posting Date', 'Buchungsdatum', 'Date'],
        'description': ['Material Description', 'Materialkurztext', 'CostCenter']
    },
    'utility': {
        'meter_id': ['Meter Number', 'Meter ID', 'Meter No', 'MeterID'],
        'start_date': ['Period Start', 'Start Date', 'From Date', 'BillStartDate'],
        'end_date': ['Period End', 'End Date', 'To Date', 'BillEndDate'],
        'consumption': ['Consumption', 'Usage'],
        'unit': ['Unit', 'UOM']
    },
    'travel': {
        'travel_type': ['TravelType', 'Travel Type', 'Type', 'Mode'],
        'origin': ['Origin', 'Departure', 'From'],
        'destination': ['Destination', 'Arrival', 'To'],
        'class': ['Class', 'Cabin', 'Seat Class'],
        'date': ['Flight Date', 'Departure Date', 'Date'],
        'distance': ['Distance', 'Dist', 'Miles', 'Kilometers'],
        'unit': ['Unit', 'UOM'],
        'hotel_nights': ['HotelNights', 'Hotel Nights', 'Nights'],
        'employee_id': ['EmployeeID', 'Employee ID', 'Employee'],
    }
}
