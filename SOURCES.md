# Data Sources & Real-World Formats

This document details the research conducted on the three primary data sources, the assumptions made for our sample data, and the potential breaking points in a real-world deployment.

## 1. SAP Export (Fuel/Electricity Data)
### Real-World Format Researched
In the real world, SAP data is usually exported via the SAP GUI (ALV Grid) into a CSV or Excel format. These exports often contain heavy metadata headers (e.g., user who ran the report, timestamp, SAP module version) before the actual tabular data begins.
### What We Learned
We learned that SAP ALV exports are notoriously inconsistent. Columns can be rearranged based on individual user layouts, and numerical formatting changes based on the user's locale (e.g., `1.000,50` vs `1,000.50`). 
### Our Sample Data
Our sample data (`sap_export_sample.csv`) uses a normalized structure with fixed headers: `Transaction Code`, `Material`, `Quantity`, `UOM`, and `Date`. We assumed the file has already been pre-processed to remove metadata headers.
### What Would Break
Our parser would break if the SAP user exports the ALV grid using a German locale, where commas are used as decimal separators, causing the Python float conversion to throw a `ValueError`. It would also break if the user rearranged the columns and the export did not include the exact header names we mapped.

## 2. Utility Bills (Electricity)
### Real-World Format Researched
Real-world utility data rarely comes in a clean CSV directly from the provider. It is usually extracted from PDFs via OCR or received via Electronic Data Interchange (EDI) feeds through third-party bill aggregators like Urjanet.
### What We Learned
Utility billing cycles do not cleanly align with calendar months. A bill might run from `Jan 14` to `Feb 13`. Allocating those emissions accurately requires prorating the consumption across the two months. Furthermore, utility bills often contain adjustments or reversals from previous months.
### Our Sample Data
Our sample data (`utility_bill_sample.csv`) simulates a flattened feed from a bill aggregator, containing `Provider`, `Meter Number`, `Start Date`, `End Date`, and `Total kWh`. We allocated the emissions to the `End Date` for simplicity.
### What Would Break
The deployment would break if the utility provider sends dates in an ambiguous format (e.g., `05/06/2024` — is it May 6 or June 5?) and our parser defaults to the wrong datetime locale. It would also break if the provider includes a "reversal" row with a negative kWh value, which might violate unsigned constraints in our database schema.

## 3. Travel Provider (Flights)
### Real-World Format Researched
Data from corporate travel providers (e.g., Concur, Egencia) usually comes in massive, multi-tabbed reports detailing every aspect of a trip: car rentals, hotel stays, and multi-leg flights.
### What We Learned
Carbon calculations for flights require knowing the exact flight class (Economy, Business, First) because the carbon footprint per passenger varies drastically based on the space they occupy on the plane. Furthermore, calculating distance from a CSV usually requires mapping IATA airport codes (e.g., JFK to LHR) to a geospatial database to calculate the Haversine distance.
### Our Sample Data
Our sample (`travel_sample.csv`) is highly simplified. It assumes the travel provider has already calculated the total distance of the trip. It provides `Trip ID`, `Employee ID`, `Flight Class`, `Distance`, and `Date`.
### What Would Break
In a real deployment, if the travel provider only gives us a "Routing" string (e.g., `SFO-ORD-JFK`) instead of a pre-calculated distance, our parser would crash because it currently lacks the geospatial logic and airport database required to calculate the flight distance dynamically.
