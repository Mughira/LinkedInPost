# -*- encoding: utf-8 -*-
"""

"""

from flask import render_template, redirect, request, url_for
from flask_login import (
    current_user,
    login_user,
    logout_user
)
from flask_dance.contrib.github import github

from apps import db, login_manager
from apps.authentication import blueprint
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
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


# chrome_options = Options()

# # Initialize the Chrome WebDriver
# chromedriver_path = "D:\\Z\\free-flask-datta-able-master\\LinkedInPost\\apps\\authentication\\chromedriver.exe"

# driver = webdriver.Chrome(executable_path=chromedriver_path, options=chrome_options)

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")  # Run in headless mode (no GUI)
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
# Use ChromeDriverManager to handle the driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)


@blueprint.route('/')
def route_default():
    return redirect(url_for('authentication_blueprint.login'))

# Login & Registration

cookies_file = 'cookies.json'

def save_cookies(cookies_file):
    # Check if the file exists and delete it
    if os.path.exists(cookies_file):
        os.remove(cookies_file)
    
    # Get cookies from the driver
    cookies = driver.get_cookies()
    
    # Write cookies to the new file
    with open(cookies_file, 'w') as f:
        json.dump(cookies, f)

def load_cookies():
    if os.path.exists(cookies_file):
        with open(cookies_file, 'r') as f:
            cookies = json.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)


def save_to_local_storage(driver, username, password):
    driver.execute_script(f"localStorage.setItem('username', '{username}');")
    driver.execute_script(f"localStorage.setItem('password', '{password}');")

def otp_function():
    # Simulate fetching OTP, for example from SMS or email
    otp = input("Please enter the OTP: ")
    return otp

def login_to_linkedin(username, password):
    # Set up Chrome options for headless mode
    if os.path.exists(cookies_file):
        print("Loading cookies...")
        driver.get("https://www.linkedin.com")
        #time.sleep(2)
        load_cookies()
        driver.refresh()
        #time.sleep(3)
    else:

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
        save_to_local_storage(driver, email, password)
    
    try:
        # 
        # Wait for the feed page to load
        #time.sleep(5)
        print("driver.current_url: ",driver.current_url)
        
        # Check if OTP is required
        if "checkpoint/challenge" in driver.current_url:
            print("OTP required...")
            otp_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "input__phone_verification_pin")))
            # Call the otp_function to retrieve OTP (e.g., from an SMS or authenticator)
            otp_code = otp_function()
            otp_input.send_keys(otp_code)
            submit_otp = driver.find_element(by=By.XPATH, value="//button[@type='submit']")
            submit_otp.click()
            time.sleep(3)
        print("driver.current_url: ",driver.current_url)
        # Check if login is successful
        if "feed" not in driver.current_url:
            return None, "Login failed"
        
        save_cookies(cookies_file)
        return driver, "Login successful"
    
    except Exception as e:
        return None, f"An error occurred: {str(e)}"

def scrape_my_linkedin_posts(driver):
    posts_data = []

    # Navigate to your LinkedIn profile page
    driver.get("https://www.linkedin.com/in/me/")  # '/in/me/' directs to the logged-in user's profile
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
    #time.sleep(5)

    # Navigate to the "Posts" section by scrolling and clicking on the "Posts" tab
    try:
        posts_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/recent-activity/shares/')]"))
        )
        posts_tab.click()
        #time.sleep(5)
    except Exception as e:
        print(f"Failed to navigate to posts: {e}")
        return []

    # Scroll to load more posts (adjust range for more posts)
    for _ in range(3):  # Adjust range for more posts
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        #time.sleep(3)

    # Ensure posts are loaded
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "scaffold-finite-scroll__content"))
    )

    # Find all post elements
    try:
        posts = driver.find_elements(By.XPATH, "//div[contains(@class, 'scaffold-finite-scroll__content')]//div[contains(@data-urn, 'urn:li:activity')]")
        print("Number of posts found: ", len(posts))
    except Exception as e:
        print(f"Error finding posts: {e}")
        return []

    for post in posts:
        try:
            # Scrape post content
            content = post.find_element(By.XPATH, ".//span[contains(@class, 'break-words')]").text
            
            # Scrape the number of likes
            likes = post.find_element(By.XPATH, ".//span[contains(@class, 'social-details-social-counts__reactions-count')]").text
            
            # Scrape the number of comments
            comments = post.find_element(By.XPATH, ".//span[contains(@class, 'social-details-social-counts__comments')]").text

            # Collecting data
            posts_data.append({
                "content": content,
                "likes": likes,
                "comments": comments
            })
        except Exception as e:
            print(f"Failed to scrape a post: {e}")

    return posts_data


@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm(request.form)
    if 'login' in request.form:

        # read form data
        user_id  = request.form['username'] # we can have here username OR email
        password = request.form['password']
        print("Here 1")
        driver, message = login_to_linkedin(user_id, password)
        if not driver:
            print("Here 2: ", message)
        #    posts = scrape_my_linkedin_posts(driver)
        # Locate user
        user = Users.find_by_username(user_id)

        # if user not found
        if not user:

            user = Users.find_by_username(user_id)

            if not user:
                user = Users(**request.form)
                db.session.add(user)
                db.session.commit()
        # Check the password
        if verify_pass(password, user.password):

            login_user(user)
            return redirect(url_for('authentication_blueprint.route_default'))

        # Something (user or pass) is not ok
        return render_template('accounts/login.html',
                               msg='Wrong user or password',
                               form=login_form)

    if not current_user.is_authenticated:
        return render_template('accounts/login.html',
                               form=login_form)
    return redirect(url_for('home_blueprint.index'))


@blueprint.route('/register', methods=['GET', 'POST'])
def register():
    create_account_form = CreateAccountForm(request.form)
    if 'register' in request.form:

        username = request.form['username']
        email = request.form['email']

        # Check usename exists
        user = Users.query.filter_by(username=username).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Username already registered',
                                   success=False,
                                   form=create_account_form)

        # Check email exists
        user = Users.query.filter_by(email=email).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Email already registered',
                                   success=False,
                                   form=create_account_form)

        # else we can create the user
        user = Users(**request.form)
        db.session.add(user)
        db.session.commit()

        # Delete user from session
        logout_user()

        return render_template('accounts/register.html',
                               msg='User created successfully.',
                               success=True,
                               form=create_account_form)

    else:
        return render_template('accounts/register.html', form=create_account_form)


@blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('authentication_blueprint.login')) 

# Errors

@login_manager.unauthorized_handler
def unauthorized_handler():
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(403)
def access_forbidden(error):
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('home/page-404.html'), 404


@blueprint.errorhandler(500)
def internal_error(error):
    return render_template('home/page-500.html'), 500
