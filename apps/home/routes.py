# -*- encoding: utf-8 -*-
"""

"""

from apps.home import blueprint
from flask import render_template, request
from flask_login import login_required
from jinja2 import TemplateNotFound

from apps import db, login_manager
from apps.authentication.forms import LoginForm, CreateAccountForm
from apps.authentication.models import Users
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from apps.authentication.util import verify_pass
import os
import json
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from meta_ai_api import MetaAI
from webdriver_manager.chrome import ChromeDriverManager

cookies_file = 'cookies.json'
# chrome_options = Options()
# chrome_options.add_argument("--headless")  # Run in headless mode (no GUI)
# chrome_options.add_argument("--no-sandbox")
# chrome_options.add_argument("--disable-dev-shm-usage")
# # Initialize the Chrome WebDriver
# chromedriver_path = "D:\\Z\\free-flask-datta-able-master\\LinkedInPost\\apps\\authentication\\chromedriver.exe"
# # 
# driver = webdriver.Chrome(executable_path=chromedriver_path, options=chrome_options)

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")  # Run in headless mode (no GUI)
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Use ChromeDriverManager to handle the driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)





def load_cookies():
    if os.path.exists(cookies_file):
        with open(cookies_file, 'r') as f:
            cookies = json.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)

def save_cookies(cookies_file):
    # Check if the file exists and delete it
    if os.path.exists(cookies_file):
        os.remove(cookies_file)
    
    # Get cookies from the driver
    cookies = driver.get_cookies()
    
    # Write cookies to the new file
    with open(cookies_file, 'w') as f:
        json.dump(cookies, f)

def login_to_linkedin(username, password):
    # Set up Chrome options for headless mode

    email = username
    password = password

    driver.get("https://www.linkedin.com/login")
    #time.sleep(1)

    eml = driver.find_element(by=By.ID, value="username")
    eml.send_keys(email)
    passwd = driver.find_element(by=By.ID, value="password")
    passwd.send_keys(password)
    loginbutton = driver.find_element(by=By.XPATH, value="//button[@type='submit']")
    loginbutton.click()
    #time.sleep(3)
    save_cookies(cookies_file)
    
    try:
        
        # Wait for the feed page to load
        #time.sleep(5)
        print("driver.current_url: ",driver.current_url)
        
        # Check if login is successful
        if "feed" not in driver.current_url:
            return None, "Login failed"
        
        return driver, "Login successful"

    except Exception as e:
        return None, f"An error occurred: {str(e)}"

def getProfileAnalytics(url):
    time.sleep(1)
    driver.get("https://www.linkedin.com/analytics/post-summary/urn:li:activity:"+url+"/")
    source = BeautifulSoup(driver.page_source, 'html.parser')
    post = source.find('div', class_='inline-show-more-text--is-collapsed-with-line-clamp')
    # if post is None:
        
    impressions = source.find_all('p', class_='text-body-medium-bold pr1 text-heading-large')
    engagements = source.find_all('div', class_='member-analytics-addon__cta-list-item-count-container')
    ai = MetaAI()
    response = ai.prompt(message="Rewrite linkedin post that you are provided to increase the engagement and impressions. engagement and impressions are "+str(impressions)+" \n\n and post is:"+str(post))
    return impressions, engagements, post, response

def getProfilePosts():
    time.sleep(1)
    driver.get("https://www.linkedin.com/in/me/recent-activity/all/")

    # Scroll down to load all posts
    prev_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == prev_height:
            break
        prev_height = new_height
    print("Waiting for page to load...")
    time.sleep(3)
    print("Done loading...")

    source = BeautifulSoup(driver.page_source, 'html.parser')
    posts = []
    # with open('source.html', 'w') as f:
    #     f.write(str(source))
    post_elements = source.find_all('li', class_='profile-creator-shared-feed-update__container')
    for post in post_elements:
        post_data = {}
        post_data['description'] = post.find('div', class_='update-components-text relative update-components-update-v2__commentary')
        post_data['comments'] = post.find('span', class_='social-details-social-counts__reactions-count')
        post_data['likes'] = post.find('span', class_='social-details-social-counts__reactions-count')
        post_data['analytics'] = post.find('div', class_='content-analytics-entry-point')
        
        # post_data['likes'] = ''
        # post_data['comments'] = []
        # comment_elements = post.find_all('li', class_='social-details-social-counts__item')
        # for comment in comment_elements:
        #     if 'comment' in comment.text.lower():
        #         post_data['comments'] = [c.strip() for c in comment.text.split('·') if 'comment' in c.lower()]

        posts.append(post_data)
    return posts

@blueprint.route('/index')
def index():
    driver.get("https://www.linkedin.com")
    time.sleep(2)
    load_cookies()
    driver.refresh()
    posts = getProfilePosts()
    print("posts: " ,posts)
    return render_template('home/index.html', segment='index', posts=posts)


@blueprint.route('/analytics/post-summary/urn:li:activity:<string:id>/', methods=['GET'])
def post_summary(id):
    print("Dynamic ID:", id)
    driver.get("https://www.linkedin.com")
    load_cookies()
    driver.refresh()
    impressions, engagements, post, response = getProfileAnalytics(id)
    print("response: ",response)
    return render_template('home/index1.html', segment='index', impressions = impressions, post = post, response = response['message'])





@blueprint.route('/<template>')
@login_required
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)
        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'index'

        return segment

    except:
        return None
