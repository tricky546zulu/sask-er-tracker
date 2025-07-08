import requests
import pdfplumber
import pandas as pd
from datetime import datetime
import pytz
import io # <-- REQUIRED: Import the io library

# URL of the PDF file
PDF_URL = "https://www.ehealthsask.ca/reporting/Documents/SaskatoonHospitalBedCapacity.pdf"

# File paths
TEMPLATE_PATH = 'template.html'
OUTPUT_PATH = 'index.html'

def download_pdf(url):
    """Downloads the PDF from the given URL and returns a file-like object."""
    print("Downloading PDF...")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        print("Download successful.")
        # FIX: Wrap the downloaded bytes in an io.BytesIO object
        # This makes it behave like a file, which pdfplumber needs.
        return io.BytesIO(response.content)
    except requests.exceptions.RequestException as e:
        print(f"Error downloading PDF: {e}")
        return None

def parse_emergency_data(pdf_content_stream):
    """Parses the PDF content stream to find emergency department stats."""
    print("Parsing PDF for Emergency Department data...")
    all_hospitals_data = []
    
    target_hospitals = [
        "Royal University Hospital", 
        "Saskatoon City Hospital", 
        "Jim Pattison Children's Hospital"
    ]
    
    try:
        with pdfplumber.open(pdf_content_stream) as pdf:
            page = pdf.pages[0]
            text = page.extract_text(x_tolerance=2, y_tolerance=2)
            lines = text.split('\n')

            current_hospital = None
            hospital_data_map = {name: {"name": name, "stats": {}} for name in target_hospitals}

            for line in lines:
                # Check if the line indicates a new hospital section
                for hospital_name in target_hospitals:
                    if hospital_name in line:
                        current_hospital = hospital_name
                        print(f"--- Found section for: {current_hospital} ---")
                        break
                
                # If we are inside a hospital block, look for ED data
                if current_hospital and "Emergency Department" in line:
                    print(f"Found 'Emergency Department' line for {current_hospital}: '{line}'")
                    if ':' in line:
                        parts = line.split(':', 1)
                        key = parts[0].replace("Emergency Department", "").strip()
                        value = parts[1].strip()
                        hospital_data_map[current_hospital]["stats"][key] = value
                        print(f"  - Parsed Stat: '{key}': '{value}'")
            
            # Convert map to list, only including hospitals where we found stats
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
        return "<p class='text-danger'><b>Error:</b> Could not parse emergency department data from the PDF. The source format may have changed or the file is unavailable.</p>"

    rows = []
    for hospital in data:
        row = {'Hospital': hospital['name']}
        row.update(hospital['stats'])
        rows.append(row)
    
    if not rows:
        return "<p>No data could be extracted. Check scraper logs in the GitHub Actions tab for more details.</p>"

    df = pd.DataFrame(rows).fillna('N/A')
    
    if 'Hospital' in df.columns:
        cols = ['Hospital'] + [col for col in df.columns if col != 'Hospital']
        df = df[cols]
    
    return df.to_html(index=False, classes='table table-striped table-hover', justify='left', border=0)

def main():
    """Main function to run the scraper and update the HTML."""
    pdf_stream = download_pdf(PDF_URL)
    
    sask_time = datetime.now(pytz.timezone('Canada/Saskatchewan'))
    update_time = sask_time.strftime('%B %d, %Y at %I:%M:%S %p %Z')

    if not pdf_stream:
        print("Stopping script as PDF download failed.")
        html_table = "<p class='text-danger'><b>Error:</b> Failed to download the data source PDF. The source may be temporarily unavailable.</p>"
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
