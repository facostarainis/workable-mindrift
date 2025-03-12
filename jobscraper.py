from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import os

# Configure Chrome options
chrome_options = Options()
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--remote-debugging-port=9222")
chrome_options.add_argument("--headless=new")  # Run in headless mode
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")  # Ensure proper rendering in headless mode
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Prevent detection as a bot

# Initialize WebDriver
driver = webdriver.Chrome(options=chrome_options)

# Define CSV path
csv_file = 'toloka_ai_jobs.csv'

# Load existing CSV
if os.path.exists(csv_file):
    df = pd.read_csv(csv_file)
else:
    print("CSV file not found. Exiting.")
    exit()

# Identify rows where Description, Requirements, or Benefits are missing
missing_details_df = df[(df['Description'].isna()) | (df['Requirements'].isna()) | (df['Benefits'].isna())]

if missing_details_df.empty:
    print("No missing job details found. Exiting.")
    driver.quit()
    exit()

print(f"Found {len(missing_details_df)} jobs with missing details. Starting to scrape...")

# Iterate through missing jobs and scrape details
for idx, job in missing_details_df.iterrows():
    print(f"Scraping details for job ID {job['ID']} - {idx+1}/{len(missing_details_df)}")

    driver.get(job['Apply Link'])
    time.sleep(3)  # Wait for the page to load

    # Handle cookie consent
    try:
        cookie_decline_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Decline all')]"))
        )
        cookie_decline_button.click()
        time.sleep(2)
    except (NoSuchElementException, TimeoutException):
        pass  # No cookie pop-up detected

    # Scrape job details
    job_soup = BeautifulSoup(driver.page_source, 'html.parser')
    main_section = job_soup.find('main', {'role': 'main'})
    
    if main_section:
        for section in main_section.find_all('section'):
            header = section.find('h2')
            if header:
                column_name = header.get_text(strip=True)
                section_content = section.get_text(separator='\n', strip=True).replace(header.get_text(strip=True), '').strip()

                if column_name in ['Description', 'Requirements', 'Benefits']:
                    df.loc[df['ID'] == job['ID'], column_name] = section_content
                    print(f"Updated {column_name} for job ID {job['ID']}")

    # Save updated data after each job
    df.to_csv(csv_file, index=False)

driver.quit()
print("Finished fixing missing job details.")
