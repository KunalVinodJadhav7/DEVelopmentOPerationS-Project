import os
import time
import uuid
import unittest
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:8000')
REMOTE_URL = os.getenv('SELENIUM_REMOTE_URL', '')
SCREENSHOT_DIR = Path(os.getenv('SCREENSHOT_DIR', 'test-results/screenshots'))
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class LeaveApprovalWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1440,1000')

        if REMOTE_URL:
            cls.driver = webdriver.Remote(command_executor=REMOTE_URL, options=options)
        else:
            for binary in ('/usr/bin/chromium', '/usr/bin/google-chrome', '/usr/bin/chromium-browser'):
                if Path(binary).exists():
                    options.binary_location = binary
                    break
            cls.driver = webdriver.Chrome(options=options)

        cls.wait = WebDriverWait(cls.driver, 15)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'driver', None):
            cls.driver.quit()

    def setUp(self):
        self.username = f'ui_{uuid.uuid4().hex[:8]}'
        self.email = f'{self.username}@example.com'
        self.password = 'Passw0rd!'

    def tearDown(self):
        result = getattr(getattr(self, '_outcome', None), 'result', None)
        if not result:
            return
        failures = list(result.failures) + list(result.errors)
        if any(test is self and err for test, err in failures):
            path = SCREENSHOT_DIR / f'{self._testMethodName}.png'
            try:
                self.driver.save_screenshot(str(path))
            except Exception:
                pass

    def wait_click(self, css):
        element = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
        element.click()
        return element

    def register_and_login(self):
        self.driver.get(f'{BASE_URL}/dashboard')
        self.wait_click('.tabs button:nth-child(2)')
        self.driver.find_element(By.CSS_SELECTOR, '#registerForm input[name="username"]').send_keys(self.username)
        self.driver.find_element(By.CSS_SELECTOR, '#registerForm input[name="email"]').send_keys(self.email)
        self.driver.find_element(By.CSS_SELECTOR, '#registerForm input[name="password"]').send_keys(self.password)
        self.driver.find_element(By.CSS_SELECTOR, '#registerForm button').click()
        self.wait.until(EC.visibility_of_element_located((By.ID, 'loginForm')))

        self.driver.find_element(By.CSS_SELECTOR, '#loginForm input[name="username"]').send_keys(self.username)
        self.driver.find_element(By.CSS_SELECTOR, '#loginForm input[name="password"]').send_keys(self.password)
        self.driver.find_element(By.CSS_SELECTOR, '#loginForm button').click()
        self.wait.until(EC.url_contains('/employee'))

    def test_dashboard_loads(self):
        self.driver.get(f'{BASE_URL}/dashboard')
        self.assertEqual('LeaveFlow | Sign in', self.driver.title)
        self.assertTrue(self.driver.find_element(By.ID, 'loginForm').is_displayed())
        self.assertTrue(self.driver.find_element(By.ID, 'registerForm').is_displayed() is False)

    def test_employee_registration_and_login(self):
        self.register_and_login()
        self.assertIn('/employee', self.driver.current_url)
        self.assertIn('Apply for leave', self.driver.find_element(By.TAG_NAME, 'h1').text)

    def test_employee_submits_leave_request(self):
        self.register_and_login()
        self.driver.execute_script("arguments[0].value = '2026-10-01';", self.driver.find_element(By.NAME, 'start_date'))
        self.driver.execute_script("arguments[0].value = '2026-10-03';", self.driver.find_element(By.NAME, 'end_date'))
        self.driver.find_element(By.NAME, 'reason').send_keys('Selenium integration test')
        self.driver.find_element(By.CSS_SELECTOR, '#leaveForm button[type="submit"]').click()

        alert = self.wait.until(EC.visibility_of_element_located((By.ID, 'leaveAlert')))
        self.assertIn('Leave request submitted successfully', alert.text)
        self.assertIn('PENDING HR', self.driver.find_element(By.TAG_NAME, 'body').text)


if __name__ == '__main__':
    unittest.main()
