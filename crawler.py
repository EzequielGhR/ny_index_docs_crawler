import logging
import argparse
import json

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from time import sleep, time_ns

SITE = "https://iapps.courts.state.ny.us/webcivil/FCASSearch?param=I"


def check_for_captcha(driver:webdriver.chrome.webdriver.WebDriver) -> None:
    try:
        sleep(10)
        driver.find_element(By.NAME, "captcha_form")
        logging.info("captcha found")
        input("please hit enter when captcha is solved")
    except NoSuchElementException:
        pass

def check_for_docs(driver:webdriver.chrome.webdriver.WebDriver) -> bool:
    try:
        driver.find_element(By.NAME, "showEfiledButton").click()
        return True
    except NoSuchElementException:
        logging.info("No docs found")
        return False

def ny_crawler(case_number:str, debug:bool=False) -> dict:
    #initialize metrics:
    output = {"input_case_number": case_number, "data": [], "cases": 0}

    #Set up pdf download options
    options = webdriver.ChromeOptions()
    options.add_experimental_option('prefs', {
        "download.default_directory": "/app/docs/{}".format(case_number.replace("/", "_")), #TODO: Make this more flexible
        "download.prompt_for_download": False, #To auto download the file
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True #It will not show PDF directly in chrome
    })

    #initialize driver
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    driver.get(SITE)
    logging.info("accessing site '{}'".format(SITE))
    handles = {"case_search": driver.window_handles[0]}
    #wait for captcha
    check_for_captcha(driver)
    #input case number
    driver.find_element(By.ID, "txtIndex").send_keys(case_number)
    driver.find_element(By.CSS_SELECTOR, "input.normal").click()
    check_for_captcha(driver)

    rows = driver.find_elements(
        By.CSS_SELECTOR,
        "#showForm > tbody > tr:nth-child(5) > td > table:nth-child(3) > tbody > tr > td:nth-child(1) > span > a"
    )

    for row in rows:
        #initialize docs counter
        docs_per_case = 0

        row.click()
        check_for_captcha(driver)
        handles['case_info'] = driver.window_handles[-1]
        driver.switch_to.window(handles['case_info'])
        if check_for_docs(driver):
            handles['case_docs'] = driver.window_handles[-1]
            driver.switch_to.window(handles['case_docs'])
            docs = driver.find_elements(
                By.CSS_SELECTOR,
                "body > table > tbody > tr > td:nth-child(2) > table > tbody > tr > td > table:nth-child(6) > "\
                    +"tbody > tr:nth-child(1) > td > table > tbody > tr > td > span > a"
            )

            if debug:
                docs = docs[:3]
                
            for doc in docs:
                doc.click()
                driver.switch_to.window(driver.window_handles[-1])
                sleep(3) #TODO: download by batches and implement reliable wait times
                driver.close()
                driver.switch_to.window(handles['case_docs'])
                docs_per_case += 1
        
        driver.close()
        driver.switch_to.window(handles['case_info'])
        driver.close()
        driver.switch_to.window(handles['case_search'])
        output['cases'] += 1
        output['data'] += {'case_number': 'TODO', 'docs': docs_per_case}
    
    driver.close()
    driver.quit()
    
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-number", type=str, help="case index number to search")
    parser.add_argument("--debug", type=bool, help="debug boolean parameter")

    args = parser.parse_args()
    index_number = args.index_number
    debug = args.debug

    output = ny_crawler(index_number, debug)

    with open("output_{}.json".format(time_ns()), "w") as f:
        f.write(json.dumps(output))