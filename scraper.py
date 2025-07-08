import requests
import pdfplumber
import pandas as pd
from datetime import datetime
import pytz
import io
import re

# URL of the PDF file
PDF_URL = "https://www.ehealthsask.ca/reporting/Documents/SaskatoonHospitalBedCapacity.pdf"

# File paths
TEMPLATE_PATH = 'template.html'
OUTPUT_PATH = 'index.html'

def download_pdf(url):
    """Downloads the PDF and returns a file-like object."""
    print("Downloading PDF...")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        print("Download successful.")
        return io.BytesIO(response.content)
    except requests.exceptions.RequestException as e:
        print(f"Error downloading PDF: {e}")
        return None

def parse_emergency_data(pdf_stream):
    """
    Parses the PDF with a more resilient logic that is less dependent on layout.
    """
    print("Parsing PDF for Emergency Department data...")
    
    try:
        with pdfplumber.open(pdf_stream) as pdf:
            page = pdf.pages[0]
            lines = page.extract_text(x_tolerance=2, y_tolerance=2).split('\n')

            hospitals = ["Royal University Hospital", "Saskatoon City Hospital", "Jim Pattison Children's Hospital"]
            stats_keywords = ["Patients in Department", "Waiting for Inpatient Bed"]
            
            hospital_data_map = {name: {"name": name, "stats": {}} for name in hospitals}
            current_hospital = None

            for line in lines:
                # Check if the line indicates a new hospital section
                for hospital_name in hospitals:
                    if hospital_name in line:
                        current_hospital = hospital_name
                        print(f"--- Switched to section: {current_hospital} ---")
                        break
                
                # If we are in a hospital section, check for our keywords
                if current_hospital:
                    for keyword in stats_keywords:
                        if keyword in line:
                            # Found a line with a keyword, now find the number
                            match = re.search(r'(\d+)', line)
                            if match:
                                value = match.group(1)
                                # Avoid overwriting already found data for this hospital
                                if keyword not in hospital_data_map[current_hospital]['stats']:
                                    hospital_data_map[current_hospital]['stats'][keyword] = value
                                    print(f"  - Parsed Stat: '{keyword}' for {current_hospital}: '{value}'")

            # Convert the map to a list, only including hospitals where we found stats
            all_hospitals_data = [data for name, data in hospital_data_map.items() if data['stats']]

    except Exception as e:
        print(f"An error occurred during PDF parsing: {e}")
        import traceback
        traceback.print_exc()
        return []

    print(f"Final parsed data: {all_hospitals_data}")
    return all_hospitals_data

def generate_html_table(data):
    """Generates an HTML table from the parsed data."""
    if not data:
        return "<p class='text-danger'><b>No data available.</b> The scraper ran successfully but could not extract any statistics from the source PDF. The format may have temporarily changed.</p>"

    records = []
    for item in data:
        record = {'Hospital': item['name']}
        record.update(item['stats'])
        records.append(record)
    
    df = pd.DataFrame(records).fillna('N/A')
    
    column_order = ['Hospital', 'Patients in Department', 'Waiting for Inpatient Bed']
    existing_columns = [col for col in column_order if col in df.columns]
    df = df[existing_columns]
    
    return df.to_html(index=False, classes='table table-striped table-hover', justify='left', border=0)

def main():
    """Main function to run the scraper and update the HTML."""
    pdf_stream = download_pdf(PDF_URL)
    
    sask_time = datetime.now(pytz.timezone('Canada/Saskatchewan'))
    update_time = sask_time.strftime('%B %d, %Y at %I:%M:%S %p %Z')

    if not pdf_stream:
        html_table = "<p class='text-danger'><b>Error:</b> Failed to download the data source PDF.</p>"
    else:
        er_data = parse_emergency_data(pdf_stream)
        html_table = generate_html_table(er_data)
        
    try:
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            template = f.read()
    except FileNotFoundError:
        print(f"FATAL ERROR: template.html not found.")
        return
            
    final_html = template.replace('{{data_table}}', html_table)
    final_html = final_html.replace('{{update_time}}', update_time)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(final_html)
    print(f"Successfully generated {OUTPUT_PATH} at {update_time}")

if __name__ == '__main__':
    main()
