import requests
import pdfplumber
import pandas as pd
from datetime import datetime
import pytz # For timezone handling

# URL of the PDF file
PDF_URL = "https://www.ehealthsask.ca/reporting/Documents/SaskatoonHospitalBedCapacity.pdf"

# File paths
TEMPLATE_PATH = 'template.html'
OUTPUT_PATH = 'index.html'

def download_pdf(url):
    """Downloads the PDF from the given URL and returns its content."""
    print("Downloading PDF...")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes
        print("Download successful.")
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error downloading PDF: {e}")
        return None

def parse_emergency_data(pdf_content):
    """Parses the PDF content to find emergency department stats."""
    print("Parsing PDF for Emergency Department data...")
    all_hospitals_data = []

    try:
        with pdfplumber.open(pdf_content) as pdf:
            page = pdf.pages[0] # Assuming data is on the first page
            text = page.extract_text()
            lines = text.split('\n')

            hospitals = ["Royal University Hospital", "Saskatoon City Hospital", "Jim Pattison Children's Hospital"]

            for hospital_name in hospitals:
                hospital_data = {"name": hospital_name, "stats": {}}
                try:
                    # Find the starting line for the hospital block
                    start_index = lines.index(hospital_name)
                    # Define a search area to avoid finding "Emergency Department" from other sections
                    search_block = lines[start_index:start_index + 20]

                    ed_found = False
                    for i, line in enumerate(search_block):
                        if "Emergency Department" in line:
                            # The data we want is in the lines immediately following this header
                            data_lines = search_block[i+1:i+5]
                            for data_line in data_lines:
                                if ':' in data_line:
                                    key, value = data_line.split(':', 1)
                                    hospital_data["stats"][key.strip()] = value.strip()
                            ed_found = True
                            break

                    if ed_found:
                        all_hospitals_data.append(hospital_data)
                        print(f"Successfully parsed data for {hospital_name}.")
                    else:
                        print(f"Could not find Emergency Department section for {hospital_name}.")

                except ValueError:
                    print(f"Could not find hospital block for: {hospital_name}")
                    continue

    except Exception as e:
        print(f"An error occurred during PDF parsing: {e}")
        return []

    return all_hospitals_data

def generate_html(data):
    """Generates an HTML table from the parsed data."""
    if not data:
        return "<p>No data could be parsed from the PDF. The source format may have changed or the file is unavailable.</p>"

    # Using pandas to easily create an HTML table
    rows = []
    for hospital in data:
        row = {'Hospital': hospital['name']}
        row.update(hospital['stats'])
        rows.append(row)

    df = pd.DataFrame(rows)
    # Reorder columns to be more logical
    cols = ['Hospital'] + [col for col in df.columns if col != 'Hospital']
    df = df[cols]

    # Convert DataFrame to HTML, add some styling classes
    return df.to_html(index=False, classes='table table-striped', justify='left')

def main():
    """Main function to run the scraper and update the HTML."""
    pdf_bytes = download_pdf(PDF_URL)
    if not pdf_bytes:
        print("Stopping script as PDF download failed.")
        # We can still write an update to the page to show failure
        html_content = "<p>Failed to download the data source PDF at this time.</p>"
        update_time = datetime.now(pytz.timezone('Canada/Saskatchewan')).strftime('%Y-%m-%d %I:%M:%S %p %Z')
    else:
        er_data = parse_emergency_data(pdf_bytes)
        html_table = generate_html(er_data)
        update_time = datetime.now(pytz.timezone('Canada/Saskatchewan')).strftime('%Y-%m-%d %I:%M:%S %p %Z')

    # Read the template
    with open(TEMPLATE_PATH, 'r') as f:
        template = f.read()

    # Replace placeholders
    final_html = template.replace('{{data_table}}', html_table)
    final_html = final_html.replace('{{update_time}}', update_time)

    # Write the final HTML
    with open(OUTPUT_PATH, 'w') as f:
        f.write(final_html)
    print(f"Successfully generated {OUTPUT_PATH} at {update_time}")

if __name__ == '__main__':
    main()

