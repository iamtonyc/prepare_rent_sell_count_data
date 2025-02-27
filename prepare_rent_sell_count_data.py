import datetime
import sys
import re
import pandas as pd
import time
import os
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.errors import HttpError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='rent_sell_count.log'
)
logger = logging.getLogger(__name__)

url_map = {
    'RENT': "https://hk.centanet.com/findproperty/list/rent",
    'SELL': "https://hk.centanet.com/findproperty/list/buy",
    'WAN_CHAI_RENT': "https://hk.centanet.com/findproperty/list/rent/%E7%81%A3%E4%BB%94_19-HMA160?q=33e8505214",
    'WAN_CHAI_SELL': "https://hk.centanet.com/findproperty/list/buy/%E7%81%A3%E4%BB%94_19-HMA160?q=34d618e4ef"
}

def get_rent_sell_count(playwright, type_str: str) -> str:
    """Fetch property count with optimized Playwright usage."""
    try:
        start_time = time.time()
        url = url_map.get(type_str, "")
        if not url:
            raise ValueError(f"Invalid type: {type_str}")

        browser = playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-gpu',
                '--disable-extensions',
                '--blink-settings=imagesEnabled=false',  # Disable images
                '--disable-background-networking'
            ]
        )
        page = browser.new_page()

        logger.info(f"{type_str} - Navigating to {url}")
        for attempt in range(3):
            try:
                page.goto(url, timeout=30000, wait_until='domcontentloaded')  # 30s, wait for DOM only
                logger.info(f"{type_str} - Page navigated in {time.time() - start_time:.2f}s")
                break
            except PlaywrightTimeoutError as e:
                logger.warning(f"{type_str} - Retry {attempt+1}/3 after timeout: {str(e)}")
                print(f"{type_str} - Retry {attempt+1}/3 after timeout: {str(e)}")
                time.sleep(1)
                if attempt == 2:
                    logger.error(f"{type_str} - Failed after 3 attempts")
                    print(f"{type_str} - Failed after 3 attempts")
                    browser.close()
                    return "0"

        page.wait_for_selector('h2 span span', timeout=30000)
        element = page.query_selector('h2 span span')
        if not element:
            raise ValueError(f"{type_str} - Could not find count element")

        data = element.inner_text()
        revised_data = re.sub(r'[^\d]', '', data)
        browser.close()
        logger.info(f"{type_str} count: {revised_data}")
        print(f"{type_str} count: {revised_data}")
        print(f"{type_str} - Total time: {time.time() - start_time:.2f}s")
        return revised_data

    except Exception as e:
        logger.error(f"Error in get_rent_sell_count for {type_str}: {str(e)}")
        print(f"Error in get_rent_sell_count for {type_str}: {str(e)}")
        if 'browser' in locals():
            browser.close()
        return "0"

def main() -> str:
    """Main function with Playwright."""
    with sync_playwright() as playwright:
        try:
            logger.info("Starting data collection")
            print("Starting data collection")
            rent_data = get_rent_sell_count(playwright, 'RENT')
            sell_data = get_rent_sell_count(playwright, 'SELL')
            wan_chai_rent_data = get_rent_sell_count(playwright, 'WAN_CHAI_RENT')
            wan_chai_sell_data = get_rent_sell_count(playwright, 'WAN_CHAI_SELL')

            str_sheet_id = '1A69Ajirbxz3iuon4hahjEFA-fu63QYU_LJMhYk0WfYo'
            token_file_name = os.path.join(os.getcwd(), 'token.json')

            if not os.path.exists(token_file_name):
                raise FileNotFoundError(f"Token file not found at {token_file_name}")

            scope = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/drive.file']
            creds = ServiceAccountCredentials.from_json_keyfile_name(token_file_name, scope)
            gc = gspread.authorize(creds)
            sheet = gc.open_by_key(str_sheet_id).sheet1

            rows = sheet.get_all_values()
            df = pd.DataFrame(rows)
            row_count = len(df.index)
            logger.info(f"Current row count: {row_count}")
            print(f"Current row count: {row_count}")

            today = datetime.date.today()
            data_date = today.strftime('%Y-%m-%d')
            logger.info(f"Data date: {data_date}")
            print(f"Data date: {data_date}")

            current_row = row_count if str(df[0][row_count - 1]) == data_date else row_count + 1
            sheet.update_cell(current_row, 1, data_date)
            sheet.update_cell(current_row, 2, rent_data)
            sheet.update_cell(current_row, 3, sell_data)
            sheet.update_cell(current_row, 4, wan_chai_rent_data)
            sheet.update_cell(current_row, 5, wan_chai_sell_data)
            logger.info(f"Successfully updated row {current_row}")
            print(f"Successfully updated row {current_row}")

            return "Success!"
        except Exception as e:
            logger.error(f"Error in main: {str(e)}")
            print(f"Error in main: {str(e)}")
            return f"Error: {str(e)}"

if __name__ == "__main__":
    result = main()
    print(result)