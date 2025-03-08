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
from datetime import datetime

# Configure Chrome options
chrome_options = Options()
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--remote-debugging-port=9222")
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")  # Ensure proper rendering in headless mode
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Prevent detection as a bot

# Initialize WebDriver
driver = webdriver.Chrome(options=chrome_options)

url = 'https://apply.workable.com/toloka-ai/'
driver.get(url)
time.sleep(3)

# Handle cookie consent
try:
    cookie_decline_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Decline all')]"))
    )
    cookie_decline_button.click()
    print("Cookie consent declined.")
    time.sleep(2)
except (NoSuchElementException, TimeoutException):
    print("No cookie consent pop-up detected.")

# Click "Clear filters" button if it exists
try:
    clear_filters_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, '/html/body/div/div/div/section/div/div/div[2]/div/div[2]/div[3]/a'))
    )
    clear_filters_button.click()
    print("Filters cleared.")
    time.sleep(2)
except (NoSuchElementException, TimeoutException):
    print("No filters to clear or failed to click 'Clear filters'.")

# Click "Show more" button until all jobs are loaded
while True:
    try:
        show_more_button = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, '/html/body/div/div/div/section/div/div/div[3]/button'))
        )
        if show_more_button.is_displayed() and show_more_button.is_enabled():
            driver.execute_script("arguments[0].scrollIntoView(true);", show_more_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", show_more_button)
            print("Clicked 'Show more' button")
            time.sleep(3)
        else:
            break
    except (NoSuchElementException, TimeoutException):
        break

print("Finished loading all jobs.")

# Parse the loaded HTML with BeautifulSoup
soup = BeautifulSoup(driver.page_source, 'html.parser')
driver.quit()

# Extract job listings
jobs = []
job_listings = soup.select('ul > li[data-ui="job"]')
print(f"Total jobs found: {len(job_listings)}")

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

# Define CSV path
csv_file = 'toloka_ai_jobs.csv'

# Load existing CSV if it exists
if os.path.exists(csv_file):
    existing_df = pd.read_csv(csv_file)
    existing_ids = set(existing_df['ID'])
else:
    existing_df = pd.DataFrame()
    existing_ids = set()

# Create DataFrame for new jobs
new_jobs_df = pd.DataFrame(jobs)

# Detect deleted jobs
if not existing_df.empty:
    current_ids = set(new_jobs_df['ID'])
    deleted_ids = existing_ids - current_ids

    # Mark jobs as deleted if they are missing
    if deleted_ids:
        print(f"Marking {len(deleted_ids)} jobs as deleted.")
        for job_id in deleted_ids:
            existing_df.loc[existing_df['ID'] == job_id, 'Deleted at'] = scraping_date

    # Mark jobs as reposted if they reappear after being deleted
    for job_id in current_ids:
        if job_id in existing_ids:
            deleted_at = existing_df.loc[existing_df['ID'] == job_id, 'Deleted at']
            reposted_at = existing_df.loc[existing_df['ID'] == job_id, 'Reposted at']
            
            # If it was deleted before, keep the deleted date and mark reposted date
            if not pd.isna(deleted_at).all():
                existing_df.loc[existing_df['ID'] == job_id, 'Reposted at'] = scraping_date

            # If deleted again after reposting, update deleted date
            if not pd.isna(reposted_at).all() and job_id not in current_ids:
                existing_df.loc[existing_df['ID'] == job_id, 'Deleted at'] = scraping_date

# Merge new data with existing data
merged_df = pd.concat([existing_df, new_jobs_df[~new_jobs_df['ID'].isin(existing_ids)]], ignore_index=True)

# Save merged data to CSV
merged_df.to_csv(csv_file, index=False)
print(f"Merged main job listings saved to {csv_file}.")

# Scrape individual job pages for new jobs only
for idx, job in new_jobs_df.iterrows():
    if job['ID'] not in existing_ids:
        print(f"Scraping details for job ID {job['ID']}")
        driver.get(job['Apply Link'])
        time.sleep(3)

        # Handle cookie consent
        try:
            cookie_decline_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Decline all')]"))
            )
            cookie_decline_button.click()
            time.sleep(2)
        except (NoSuchElementException, TimeoutException):
            pass

        # Scrape job details
        job_soup = BeautifulSoup(driver.page_source, 'html.parser')
        main_section = job_soup.find('main', {'role': 'main'})
        if main_section:
            for section in main_section.find_all('section'):
                header = section.find('h2')
                if header:
                    column_name = header.get_text(strip=True)
                    section_content = section.get_text(separator='\n', strip=True).replace(header.get_text(strip=True), '').strip()
                    merged_df.loc[merged_df['ID'] == job['ID'], column_name] = section_content

        # Save updated data after each job
        merged_df.to_csv(csv_file, index=False)

driver.quit()
print("Finished scraping individual job details.")

