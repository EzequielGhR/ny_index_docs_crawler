import logging
import deathbycaptcha
import json
import pandas as pd

from io import StringIO
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from time import sleep, time_ns

SITE = "https://iapps.courts.state.ny.us/webcivil/FCASSearch?param=I"
DBC_USER = "zeke_develop"
DBC_PASS = "Sonambulos102"

def solve_captcha(driver:webdriver.Chrome, dbc_username:str, dbc_password:str) -> None:
    """
    Solve page captchas using a DeathByCaptcha account.
    Params:
        - driver: Selenium's Chrome webdriver.
        - dbc_username: Username for the DeathByCaptchaAccount.
        - dbc_password: Password for the DeathByCaptchaAccount.
    """
    wait = WebDriverWait(driver, 10)

    try:
        frames = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "iframe")))

        source = ''
        for frame in frames:
            if frame.get_attribute('title').lower().strip() == 'recaptcha':
                source = frame.get_attribute('src')
            break

        site_key = source.split('k=')[-1].split('&')[0]
        url = driver.current_url

        json_ = json.dumps({
            "proxy": "",
            "proxytype": "http",
            "googlekey": site_key,
            "page_url": url
        })

        client = deathbycaptcha.SocketClient(dbc_username, dbc_password)

        captcha = client.decode(type=4, token_params=json_)
        if not captcha:
            #TODO: something here
            raise Exception("Error solving captcha")

        logging.info("Captcha '{}' solved: '{}'".format(captcha['captcha'], captcha('text')))
        solution = captcha['text']
        driver.execute_script("document.getElementById('g-recaptcha-response').innerHTML='{}'".format(solution))

        #TODO: Finish up, probably click an input
    
    except deathbycaptcha.AccessDeniedException as e:
        logging.warning("Error: Access to DBCC API denied, check your accounty balance and/or credentials")
        raise e
        
    except TimeoutException as e:
        logging.info("Captcha not found.")
    
def check_for_captcha(driver:webdriver.Chrome, dbc_user:str, dbc_pass:str) -> None:
    """
    Temporary function for debug purposes
    """
    try:
        solve_captcha(driver, dbc_user, dbc_pass)
    except deathbycaptcha.AccessDeniedException:
        input("solve captcha manually and hit enter on this box")

def check_for_docs(driver) -> bool:
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

def extract_general_data(driver:webdriver.Chrome):
    """
    A function that extracts general data about a case
    """
    general_data = {
        'court': '',
        'index number': '',
        'case name': '',
        'case type': '',
        'track': '',
        'rji filed': '',
        'date noi due': '',
        'noi filed': '',
        'disposition date': '',
        'calendar number': '',
        'jury status': '',
        'justice name': ''
    }
    tds = driver.find_elements(By.CSS_SELECTOR, "body > table > tbody > tr > td > table > tbody > tr > td")
    
    for j, td in enumerate(tds):
        for key in general_data.keys():
            if (key+':') in td.text.strip().lower():
                general_data[key] = tds[j+1].text.strip()
                break

    return general_data

def check_for_button(driver, button_name:str) -> bool:
    """
    Returns True if a case has documents, False if it doesn't
    Params:
        - driver: Selenium's Chrome webdriver
        - button
    """
    try:
        driver.find_element(By.NAME, button_name).click()
        return True
    except NoSuchElementException:
        logging.info("No button '{}' found".format(button_name))
        return False

def extract_attorneys(driver:webdriver.Chrome, plaintiff:bool=True) -> dict:
    atty_table = '<table>'+driver.find_element(
        By.CSS_SELECTOR,
        'body > table > tbody > tr > td:nth-child(2) > table:nth-child(5)'
    ).get_attribute('innerHTML')+'</table>'
    
    df = pd.read_html(StringIO(atty_table))[0].dropna(subset=[0])

    output = {
        'plaintiff': [],
        'defendant': []
    }

    for _, row in df.iterrows():
        if 'plaintiff' in row[0].lower():
            plaintiff = True
            continue
        if 'defendant' in row[0].lower():
            plaintiff=False
            continue
        if row[0] == row[1]:
            output["plaintiff" if plaintiff else "defendant"][-1]["direction"] = row[0]
            continue
        output["plaintiff" if plaintiff else "defendant"].append({"atty": row[0]})
    
    return output