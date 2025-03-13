from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import os

# Configure Chrome options
chrome_options = Options()
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--remote-debugging-port=9222")
chrome_options.add_argument("--headless=new")  # Run in headless mode
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")

# Initialize WebDriver
driver = webdriver.Chrome(options=chrome_options)

# Load existing CSV
csv_file = 'toloka_ai_jobs.csv'

if os.path.exists(csv_file):
    df = pd.read_csv(csv_file)
else:
    print("CSV file not found. Exiting.")
    exit()

# Ensure "Posted at" exists as the 4th column (after "ID")
if "Posted at" not in df.columns:
    df.insert(3, "Posted at", None)  # Insert at position 3 (4th column)

# Identify rows where Description, Requirements, or Benefits are missing (ONLY scrape "Posted at" when these are missing)
missing_details_df = df[df[['Description', 'Requirements', 'Benefits']].isna().any(axis=1)]

if missing_details_df.empty:
    print("No missing job details found. Exiting.")
    driver.quit()
    exit()

print(f"Found {len(missing_details_df)} jobs with missing details. Starting to scrape...")

# Scrape missing details
for idx, job in missing_details_df.iterrows():
    print(f"Scraping details for job ID {job['ID']} - {idx+1}/{len(missing_details_df)}")

    driver.get(job['Apply Link'])
    time.sleep(3)

    # Handle cookie consent popup
    try:
        cookie_decline_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Decline all')]"))
        )
        cookie_decline_button.click()
        time.sleep(2)
        print("Cookie consent declined.")
    except (NoSuchElementException, TimeoutException):
        print("No cookie consent pop-up detected.")

    # Parse job page
    job_soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Extract job details (Description, Requirements, Benefits)
    main_section = job_soup.find('main', {'role': 'main'})
    details_found = False

    if main_section:
        for section in main_section.find_all('section'):
            header = section.find('h2')
            if header:
                column_name = header.get_text(strip=True)
                section_content = section.get_text(separator='\n', strip=True).replace(header.get_text(strip=True), '').strip()
                if column_name in ['Description', 'Requirements', 'Benefits']:
                    df.loc[df['ID'] == job['ID'], column_name] = section_content
                    details_found = True
                    print(f"Updated {column_name} for job ID {job['ID']}")

    # Extract "Posted at" ONLY if Description, Requirements, or Benefits were scraped
    if details_found:
        try:
            script_tag = job_soup.select_one("script[type='application/ld+json']")
            if script_tag:
                job_data = json.loads(script_tag.string)
                posted_at = job_data.get("datePosted", "")
                if posted_at:
                    posted_at = pd.to_datetime(posted_at).strftime("%d/%m/%Y")  # Convert to dd/mm/yyyy format
                    df.loc[df['ID'] == job['ID'], 'Posted at'] = posted_at
                    print(f"Updated 'Posted at' for job ID {job['ID']} - {posted_at}")
        except (json.JSONDecodeError, AttributeError):
            print(f"Failed to extract 'Posted at' for job ID {job['ID']}")

    # Save after each job
    df.to_csv(csv_file, index=False)

driver.quit()
print("Finished fixing missing job details.")
