import logging
import argparse
import json
import random

from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from time import sleep, time_ns
from helper import *


def ny_crawler(input_number:str, dw_batch_size:int, proxies:list=[], debug:bool=False) -> dict:
    """
    Main documents Crawler. Returns a dictionary with the next structure:

    {
        "input_case_number": "XXXXXX",
        "data": [
            {
                "case_number": "YYYYYYY",
                "docs": N
            },
            {
                "case_number": "ZZZZZZZ",
                "docs": M
            },
            .
            .
            .
        ],
        "cases": K
    }

    Where the key "cases" has an integer value showing how many cases where found with the input case number,
    and for each element in "data", the key "docs" has an integer value showing how many documents where found
    for said case.

    Documents are stored by run on "app/docs/{input_case_number}"

    Params:
        - case_number: case number to use as input for the index search.
        - dw_batch_size: amount of documents to download by batches,
        - proxies: pool of proxies to choose at random. The format should be:
            ["http://{username}:{password}@{proxy}", ...]
        - debug: Boolean that if set to true will download a small amount of documents per case,
            just for debugging processes
    """
    #initialize metrics:
    output = {"input_case_number": input_number, "data": [], "cases": 0}

    #Set up pdf download options
    options = webdriver.ChromeOptions()
    options.add_experimental_option('prefs', {
        "download.default_directory": "/app/docs/{}".format(input_number.replace("/", "_")), #TODO: Make this more flexible
        "download.prompt_for_download": False, #To auto download the file
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True #It will not show PDF directly in chrome
    })

    #add additional arguements
    options.add_argument("--no-sandbox")
    options.add_argument("--headless")
    options.add_argument("--disable-setuid-sandbox")

    #set up rotating proxies
    if proxies:
        logging.info("proxies pool found, choosing at random")
        random_proxy = random.choice(proxies)
        seleniumwire_options = {
            "proxy": {
                "http": random_proxy,
                "https": random_proxy,
                "verify_ssl": False
            }
        }

        #initialize driver
        driver = webdriver.Chrome(
            service=ChromeService(),
            options=options,
            seleniumwire_options=seleniumwire_options
        )

    else:
        logging.warning("proxies pool not provided")
        #initialize driver
        driver = webdriver.Chrome(service=ChromeService(), options=options)

    driver.get(SITE)
    logging.info("accessing site '{}'".format(SITE))
    handles = {"case_search": driver.window_handles[0]}
    #wait for captcha
    check_for_captcha(driver) #TODO: Replace when captcha solver is ready
    #input case number
    driver.find_element(By.ID, "txtIndex").send_keys(input_number)
    driver.find_element(By.CSS_SELECTOR, "input.normal").click()
    check_for_captcha(driver) #TODO: Replace when captcha solver is ready

    rows = driver.find_elements(
        By.CSS_SELECTOR,
        "#showForm > tbody > tr:nth-child(5) > td > table:nth-child(3) > tbody > tr > td:nth-child(1) > span > a"
    )

    for row in rows:
        #initialize docs counter
        docs_per_case = 0

        row.click()
        check_for_captcha(driver) #TODO: Replace when captcha solver is ready
        handles['case_info'] = driver.window_handles[-1]
        driver.switch_to.window(handles['case_info'])

        general_data = extract_general_data(driver) #extract case general data

        #work on case documents
        if check_for_button(driver, "showEfiledButton"):
            handles['case_docs'] = driver.window_handles[-1]
            driver.switch_to.window(handles['case_docs'])
            docs = driver.find_elements(
                By.CSS_SELECTOR,
                "body > table > tbody > tr > td:nth-child(2) > table > tbody > tr > td > table:nth-child(6) > "\
                    +"tbody > tr:nth-child(1) > td > table > tbody > tr > td > span > a"
            )

            if debug:
                docs = docs[:10]

            logging.info("{} documents found for this case".format(len(docs)))
            to_close = []
            for i, doc in enumerate(docs):
                logging.info("downloading document '{}'".format(doc.text))
                doc.click()
                to_close.append(driver.window_handles[-1])
                if i%dw_batch_size == dw_batch_size-1:
                    logging.info("closing old document windows")
                    sleep(5) #TODO: wait time, maybe a fucnction parameter, or need to find better alternatives
                    for win in to_close:
                        driver.switch_to.window(win)
                        driver.close()
                driver.switch_to.window(handles["case_docs"])
                docs_per_case+=1
            
            logging.info("closing leftover windows")
            sleep(5) #TODO: wait time, maybe a fucnction parameter, or need to find better alternatives
            for win in driver.window_handles:
                if win not in handles.values():
                    driver.switch_to.window(win)
                    driver.close()
            
            driver.switch_to.window(handles["case_docs"])
            driver.close()
            driver.switch_to.window(handles["case_info"])
            driver.close()
        
        driver.switch_to.window(handles['case_search'])
        output['cases'] += 1
        general_data['docs'] = docs_per_case
        output['data'] += general_data
    
    logging.info("execution finished")
    driver.close()
    driver.quit()
    
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-number", type=str, help="case index number to search")
    parser.add_argument("--dw-batch-size", type=str, help="documents download batch size")
    parser.add_argument("--debug", type=str, help="debug boolean parameter")

    args = parser.parse_args()
    input_number = args.input_number
    dw_batch_size = eval(args.dw_batch_size)
    debug = eval(args.debug.capitalize())

    if not isinstance(dw_batch_size, int):
        raise TypeError("'dw-batch-size' param must be an integer")

    if not isinstance(debug, bool):
        raise TypeError("'debug' param must be a boolean")
    
    output = ny_crawler(input_number, dw_batch_size, debug)

    with open("output_{}.json".format(time_ns()), "w") as f:
        f.write(json.dumps(output))