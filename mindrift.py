from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
from datetime import datetime

# Configure Chrome options
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in headless mode for efficiency
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")

# Initialize WebDriver
driver = webdriver.Chrome(options=chrome_options)

url = 'https://apply.workable.com/toloka-ai/'
driver.get(url)
time.sleep(3)  # Allow time for page to load

# Handle cookie consent
try:
    cookie_decline_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Decline all')]"))
    )
    cookie_decline_button.click()
    print("Cookie consent declined.")
    time.sleep(2)  # Allow time for the page to adjust
except (NoSuchElementException, TimeoutException):
    print("No cookie consent pop-up detected.")

# Click "Show more" button until all jobs are loaded
while True:
    try:
        show_more_button = driver.find_element(By.XPATH, '/html/body/div/div/div/section/div/div/div[3]/button')
        driver.execute_script("arguments[0].scrollIntoView();", show_more_button)
        time.sleep(1)  # Allow time for the button to be scrollable
        show_more_button.click()
        time.sleep(2)  # Wait for new jobs to load
    except (NoSuchElementException, ElementClickInterceptedException):
        break  # Exit loop if button not found or no more jobs to load

# Parse the loaded HTML with BeautifulSoup
soup = BeautifulSoup(driver.page_source, 'html.parser')
driver.quit()  # Close the browser

# Extract job listings
jobs = []
job_listings = soup.select('ul > li[data-ui="job"]')

scraping_date = datetime.utcnow().strftime("%d/%m/%Y")
scraping_time = datetime.utcnow().strftime("%H:%M")

for job in job_listings:
    job_id = job.get('data-id', 'Not Provided')
    title = job.select_one('[data-ui="job-title"]').get_text(strip=True)
    workplace = job.select_one('[data-ui="job-workplace"]').get_text(strip=True) if job.select_one('[data-ui="job-workplace"]') else 'Not specified'
    location = job.select_one('[data-ui="job-location-tooltip"]').get_text(strip=True) if job.select_one('[data-ui="job-location-tooltip"]') else 'Not specified'
    department = job.select_one('[data-ui="job-department"]').get_text(strip=True) if job.select_one('[data-ui="job-department"]') else 'Not specified'
    job_type = job.select_one('[data-ui="job-type"]').get_text(strip=True) if job.select_one('[data-ui="job-type"]') else 'Not specified'
    link = 'https://apply.workable.com' + job.find('a')['href']

    jobs.append({
        'Scraping Date': scraping_date,
        'Scraping Time': scraping_time,
        'ID': job_id,
        'Deleted at': '',
        'Reposted at': '',
        'Job Title': title,
        'Workplace Type': workplace,
        'Location': location,
        'Department': department,
        'Job Type': job_type,
        'Apply Link': link
    })

# Save to CSV or update existing CSV
script_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory of the script
csv_file = os.path.join(script_dir, 'toloka_ai_jobs.csv')  # Save CSV in the same directory as the script

new_jobs_count = 0
updated_jobs_count = 0
unchanged_jobs_count = 0

if os.path.exists(csv_file):
    existing_df = pd.read_csv(csv_file)
    existing_ids = set(existing_df['ID'])
    
    # Check for deleted jobs
    current_ids = {job['ID'] for job in jobs}
    for index, row in existing_df.iterrows():
        if row['ID'] not in current_ids:
            if pd.isna(row['Deleted at']):  # Mark as deleted if not already marked
                existing_df.at[index, 'Deleted at'] = scraping_date
                updated_jobs_count += 1
        else:
            if not pd.isna(row['Deleted at']):  # Check if it's a repost
                repost_date = pd.to_datetime(row['Reposted at'], dayfirst=True, errors='coerce')
                delete_date = pd.to_datetime(row['Deleted at'], dayfirst=True, errors='coerce')
                if pd.isna(repost_date) or delete_date > repost_date:
                    existing_df.at[index, 'Reposted at'] = scraping_date
                    updated_jobs_count += 1
            else:
                unchanged_jobs_count += 1

    # Add new jobs
    new_jobs = [job for job in jobs if job['ID'] not in existing_ids]
    new_jobs_df = pd.DataFrame(new_jobs)
    new_jobs_count = len(new_jobs)
    updated_df = pd.concat([existing_df, new_jobs_df], ignore_index=True)
else:
    updated_df = pd.DataFrame(jobs)
    new_jobs_count = len(jobs)

# Ensure correct column order
column_order = [
    'Scraping Date', 'Scraping Time', 'ID', 'Deleted at', 'Reposted at',
    'Job Title', 'Workplace Type', 'Location', 'Department', 'Job Type', 'Apply Link'
]
updated_df = updated_df[column_order]

updated_df.to_csv(csv_file, index=False)

# Summary of changes
if new_jobs_count == 0 and updated_jobs_count == 0:
    print(f"No changes detected. {unchanged_jobs_count} jobs remain unchanged.")
else:
    print(f"Scraped {len(jobs)} jobs.")
    print(f"New jobs added: {new_jobs_count}")
    print(f"Updated jobs (deleted or reposted): {updated_jobs_count}")
    print(f"Unchanged jobs: {unchanged_jobs_count}")
