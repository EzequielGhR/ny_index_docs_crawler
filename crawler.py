import logging
import argparse
import deathbycaptcha
import json
import random

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException

from time import sleep, time_ns


SITE = "https://iapps.courts.state.ny.us/webcivil/FCASSearch?param=I"

def solve_captcha(driver:webdriver.chrome.webdriver.WebDriver, dbc_username:str, dbc_password:str) -> None:
    """
    Solve page captchas using a DeathByCaptcha account.
    Params:
        - driver: Selenium's Chrome webdriver.
        - dbc_username: Username for the DeathByCaptchaAccount.
        - dbc_password: Password for the DeathByCaptchaAccount.
    """
    wait = WebDriverWait(driver, 10)
    frames = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "iframe")))

    source = ''
    for frame in frames:
        if frame.get_attribute('title').lower().strip() == 'recaptcha':
            source = frame.get_attribute('src')
        break

    if source:
        site_key = source.split('k=')[-1].split('&')[0]
        url = driver.current_url

        json_ = json.dumps({
            "proxy": "",
            "proxytype": "http",
            "googlekey": site_key,
            "page_url": url
        })

        client = deathbycaptcha.SocketClient(dbc_username, dbc_password)

        try:
            captcha = client.decode(type=4, token_params=json_)
            if not captcha:
                #TODO: something here
                raise Exception("Error solving captcha")

            logging.info("Captcha '{}' solved: '{}'".format(captcha['captcha'], captcha('text')))
            solution = captcha['text']
            driver.execute_script("document.getElementById('g-recaptcha-response').innerHTML='{}'".format(solution))

            #TODO: Finish up, probably click an input
        
        except deathbycaptcha.AccessDeniedException:
            logging.warning("Error: Access to DBCC API denied, check your accounty balance and/or credentials")
    
    else:
        logging.info("Captcha not found.")

def check_for_captcha(driver:webdriver.chrome.webdriver.WebDriver) -> None:
    """
    Temporary function for debug purposes
    """
    try:
        sleep(10)
        driver.find_element(By.NAME, "captcha_form")
        logging.info("captcha found")
        input("please hit enter when captcha is solved")
    except NoSuchElementException:
        pass

def check_for_docs(driver:webdriver.chrome.webdriver.WebDriver) -> bool:
    """
    Returns True if a case has documents, False if it doesn't
    Params:
        - driver: Selenium's Chrome webdriver
    """
    try:
        driver.find_element(By.NAME, "showEfiledButton").click()
        return True
    except NoSuchElementException:
        logging.info("No docs found")
        return False

def get_proxies_pool(p_usr: str, p_pass: str, p_list:list) -> list:
    """
    Function that creates the correct proxies pool from a given proxies list
    Params:
        - p_usr: User for premium proxies account.
        - p_pass: Password for premium proxies account.
        - p_list: list of proxies

    """
    return ["http://{}:{}@{}".format(p_usr, p_pass, p) for p in p_list]


def ny_crawler(case_number:str, dw_batch_size:int, proxies:list=[], debug:bool=False) -> dict:
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
    output = {"input_case_number": case_number, "data": [], "cases": 0}

    #Set up pdf download options
    options = webdriver.ChromeOptions()
    options.add_experimental_option('prefs', {
        "download.default_directory": "/app/docs/{}".format(case_number.replace("/", "_")), #TODO: Make this more flexible
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
    driver.find_element(By.ID, "txtIndex").send_keys(case_number)
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
        if check_for_docs(driver):
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
        output['data'] += {'case_number': index_number, 'docs': docs_per_case}
    
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
    index_number = args.index_number
    dw_batch_size = eval(args.dw_batch_size)
    debug = eval(args.debug.capitalize())

    if not isinstance(dw_batch_size, int):
        raise TypeError("'dw-batch-size' param must be an integer")

    if not isinstance(debug, bool):
        raise TypeError("'debug' param must be a boolean")
    
    output = ny_crawler(index_number, dw_batch_size, debug)

    with open("output_{}.json".format(time_ns()), "w") as f:
        f.write(json.dumps(output))