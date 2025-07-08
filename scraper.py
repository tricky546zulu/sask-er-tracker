import requests
import pdfplumber
import pandas as pd
from datetime import datetime
import pytz
import io
import re # Import the regular expressions library

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
    """Parses the PDF to find emergency department stats using more robust logic."""
    print("Parsing PDF for Emergency Department data...")
    all_hospitals_data = []
    
    try:
        with pdfplumber.open(pdf_stream) as pdf:
            page = pdf.pages[0]
            lines = page.extract_text(x_tolerance=2, y_tolerance=2).split('\n')

            # Define the hospitals and the specific stats we want to find for each
            target_sections = {
                "Royal University Hospital": ["Patients in Department", "Waiting for Inpatient Bed"],
                "Saskatoon City Hospital": ["Patients in Department"],
                "Jim Pattison Children's Hospital": ["Patients in Department", "Waiting for Inpatient Bed"]
            }

            hospital_data_map = {name: {"name": name, "stats": {}} for name in target_sections}

            # Iterate through the lines of the PDF to find each hospital's data
            for i, line in enumerate(lines):
                for hospital_name, stats_to_find in target_sections.items():
                    if hospital_name in line:
                        print(f"--- Found section for: {hospital_name} ---")
                        # Define a search area of the next ~20 lines for this hospital's data
                        search_block = lines[i+1 : i+20]
                        
                        # Find the start of the Emergency Department subsection
                        ed_start_index = -1
                        for j, block_line in enumerate(search_block):
                            if "Emergency Department" in block_line:
                                ed_start_index = j
                                break

                        if ed_start_index != -1:
                            # Search for our target stats within the ED subsection
                            ed_search_area = search_block[ed_start_index:]
                            for stat_key in stats_to_find:
                                for ed_line in ed_search_area:
                                    if stat_key in ed_line:
                                        # Use regex to find any number in the line
                                        match = re.search(r'\d+', ed_line)
                                        if match:
                                            value = match.group(0)
                                            hospital_data_map[hospital_name]['stats'][stat_key] = value
                                            print(f"  - Parsed Stat: '{stat_key}': '{value}'")
                                            # Break after finding the stat to avoid double-counting
                                            break 
                        break # Move to the next line in the main PDF after processing a hospital section

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
        return "<p class='text-danger'><b>Error:</b> Could not parse valid emergency department data. The source PDF format may have changed.</p>"

    df = pd.DataFrame(data)

    # Reconstruct the DataFrame from the nested structure
    records = []
    for item in data:
        record = {'Hospital': item['name']}
        record.update(item['stats'])
        records.append(record)
    
    df = pd.DataFrame(records).fillna('N/A')
    
    # Define a logical column order
    column_order = [
        'Hospital', 
        'Patients in Department', 
        'Waiting for Inpatient Bed'
    ]
    # Filter to only columns that actually exist in the dataframe
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
