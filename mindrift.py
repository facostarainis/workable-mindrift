from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
from datetime import datetime
import requests

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
previous_jobs_count = 0  # To track if new jobs are loaded
while True:
    try:
        # Scroll to the bottom of the page to load dynamic content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # Give time for new content to load

        show_more_button = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, '/html/body/div/div/div/section/div/div/div[3]/button'))
        )

        # Check if the button is visible and clickable
        if show_more_button.is_displayed() and show_more_button.is_enabled():
            driver.execute_script("arguments[0].scrollIntoView(true);", show_more_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", show_more_button)  # Use JS click for headless mode
            print("Clicked 'Show more' button")
            time.sleep(3)  # Allow time for new jobs to load

            # Check if new jobs are loaded
            current_jobs_count = len(driver.find_elements(By.CSS_SELECTOR, 'ul > li[data-ui="job"]'))
            if current_jobs_count == previous_jobs_count:
                print("No new jobs loaded, stopping.")
                break  # Stop if no new jobs are loaded
            previous_jobs_count = current_jobs_count

        else:
            print("Button not clickable or visible.")
            break
    except (NoSuchElementException, ElementClickInterceptedException, TimeoutException) as e:
        print(f"Stopping: {str(e)}")
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

# Save main job listings to CSV immediately
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_file = os.path.join(script_dir, 'toloka_ai_jobs.csv')
pd.DataFrame(jobs).to_csv(csv_file, index=False)
print(f"Main job listings saved to {csv_file}.")

# Scrape individual job pages for new jobs
new_jobs_count = 0
for idx, job in enumerate(jobs, 1):
    print(f"Scraping individual job details ({idx}/{len(jobs)}) - {int((idx/len(jobs))*100)}% complete.")
    
    # Use Selenium to open the individual job link
    try:
        driver.get(job['Apply Link'])
        time.sleep(3)  # Wait for the page to load

        # Handle cookie consent if it appears
        try:
            cookie_decline_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Decline all')]"))
            )
            cookie_decline_button.click()
            print("Cookie consent declined for individual page.")
            time.sleep(2)
        except (NoSuchElementException, TimeoutException):
            print("No cookie consent pop-up detected on individual page.")
        
        # Parse the loaded HTML with BeautifulSoup
        job_soup = BeautifulSoup(driver.page_source, 'html.parser')

        main_section = job_soup.find('main', {'role': 'main'})
        if main_section:
            for section in main_section.find_all('section'):
                section_title = section.get('aria-labelledby')
                if section_title:
                    header = main_section.find('h2', {'id': section_title})
                    if header:
                        column_name = header.get_text(strip=True)
                        section_content = section.get_text(separator='\n', strip=True).replace(header.get_text(strip=True), '').strip()
                        job[column_name] = section_content

        new_jobs_count += 1

    except Exception as e:
        print(f"Failed to scrape individual job page {job['Apply Link']}: {e}")
        continue

# Save updated job listings with individual job details
new_jobs_df = pd.DataFrame(jobs)
new_jobs_df.to_csv(csv_file, index=False)

print(f"Scraped {len(jobs)} jobs.")
print(f"New individual jobs details added: {new_jobs_count}")

