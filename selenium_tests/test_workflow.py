import os
import unittest
import uuid
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# Week 9 browser target.
# Use http://localhost so Selenium tests the Nginx -> FastAPI path.
BASE_URL = os.getenv("BASE_URL", "http://localhost")

REMOTE_URL = os.getenv("SELENIUM_REMOTE_URL", "")

SCREENSHOT_DIR = Path(
    os.getenv(
        "SCREENSHOT_DIR",
        "test-results/screenshots",
    )
)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class LeaveApprovalWorkflowTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Create one Chrome browser for the workflow test class."""

        options = Options()

        # Headless keeps local execution automated.
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")
        options.add_argument("--disable-notifications")

        if REMOTE_URL:
            cls.driver = webdriver.Remote(
                command_executor=REMOTE_URL,
                options=options,
            )
        else:
            # Selenium Manager handles ChromeDriver discovery.
            cls.driver = webdriver.Chrome(options=options)

        cls.driver.set_page_load_timeout(30)
        cls.wait = WebDriverWait(cls.driver, 15)

    @classmethod
    def tearDownClass(cls):
        """Close the browser after all workflow tests finish."""

        driver = getattr(cls, "driver", None)

        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    def setUp(self):
        """Create unique credentials for every test."""

        self.username = f"ui_{uuid.uuid4().hex[:8]}"
        self.email = f"{self.username}@example.com"
        self.password = "Passw0rd!"

    def tearDown(self):
        """
        Save a screenshot after every workflow test.

        We intentionally do not inspect pytest's private _outcome
        object because this class uses unittest.TestCase.
        """

        driver = getattr(self.__class__, "driver", None)

        if not driver:
            return

        screenshot_name = f"{self._testMethodName}.png"
        screenshot_path = SCREENSHOT_DIR / screenshot_name

        try:
            driver.save_screenshot(str(screenshot_path))
        except Exception:
            pass

    def wait_click(self, css):
        """Wait until a CSS-selected element is clickable."""

        element = self.wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, css)
            )
        )

        element.click()
        return element

    def register_and_login(self):
        """Create a fresh employee account and sign in."""

        self.driver.get(
            f"{BASE_URL}/dashboard"
        )

        # Open Create Account tab.
        self.wait_click(
            ".tabs button:nth-child(2)"
        )

        # Registration fields.
        username_input = self.wait.until(
            EC.visibility_of_element_located(
                (
                    By.CSS_SELECTOR,
                    '#registerForm input[name="username"]',
                )
            )
        )

        email_input = self.driver.find_element(
            By.CSS_SELECTOR,
            '#registerForm input[name="email"]',
        )

        password_input = self.driver.find_element(
            By.CSS_SELECTOR,
            '#registerForm input[name="password"]',
        )

        username_input.clear()
        username_input.send_keys(self.username)

        email_input.clear()
        email_input.send_keys(self.email)

        password_input.clear()
        password_input.send_keys(self.password)

        # Submit registration.
        self.driver.find_element(
            By.CSS_SELECTOR,
            "#registerForm button",
        ).click()

        # Confirm registration succeeded.
        auth_alert = self.wait.until(
            EC.visibility_of_element_located(
                (By.ID, "authAlert")
            )
        )

        registration_message = auth_alert.text.strip()

        self.assertIn(
            "Account created",
            registration_message,
            f"Registration failed. Alert: {registration_message!r}",
        )

        # The application automatically switches back to Login.
        login_username = self.wait.until(
            EC.visibility_of_element_located(
                (
                    By.CSS_SELECTOR,
                    '#loginForm input[name="username"]',
                )
            )
        )

        login_password = self.driver.find_element(
            By.CSS_SELECTOR,
            '#loginForm input[name="password"]',
        )

        # IMPORTANT:
        # Registration JavaScript already pre-fills the username.
        # clear() prevents duplicate usernames.
        login_username.clear()
        login_username.send_keys(self.username)

        login_password.clear()
        login_password.send_keys(self.password)

        # Submit login.
        self.driver.find_element(
            By.CSS_SELECTOR,
            "#loginForm button",
        ).click()

        # Wait for either successful redirect or a NEW login error.
        def login_finished(driver):
            if "/employee" in driver.current_url:
                return ("success", "")

            alert = driver.find_element(
                By.ID,
                "authAlert",
            )

            alert_text = alert.text.strip()

            # Ignore the old registration success message.
            if not alert_text or alert_text == registration_message:
                return False

            return ("error", alert_text)

        result = self.wait.until(login_finished)

        status, detail = result

        self.assertEqual(
            "success",
            status,
            (
                "Employee login failed.\n"
                f"Current URL: {self.driver.current_url}\n"
                f"Auth alert: {detail!r}\n"
                f"Username: {self.username!r}"
            ),
        )

    def test_employee_registration_and_login(self):
        """Verify employee registration followed by login."""

        self.register_and_login()

        self.assertIn(
            "/employee",
            self.driver.current_url,
        )

        heading = self.wait.until(
            EC.visibility_of_element_located(
                (By.TAG_NAME, "h1")
            )
        )

        self.assertIn(
            "Apply for leave",
            heading.text,
        )

    def test_employee_submits_leave_request(self):
        """Verify an employee can submit a leave request."""

        self.register_and_login()

        start_date = self.driver.find_element(
            By.NAME,
            "start_date",
        )

        end_date = self.driver.find_element(
            By.NAME,
            "end_date",
        )

        reason = self.driver.find_element(
            By.NAME,
            "reason",
        )

        document = self.driver.find_element(
            By.NAME,
            "supporting_document",
        )

        document_path = (
            Path(__file__).resolve().parent
            / "test-data"
            / "supporting_document.pdf"
        )

        document.send_keys(str(document_path))

        # Set start date through the DOM and fire normal browser events.
        self.driver.execute_script(
            """
            const element = arguments[0];
            const value = arguments[1];

            const setter = Object.getOwnPropertyDescriptor(
                HTMLInputElement.prototype,
                'value'
            ).set;

            setter.call(element, value);

            element.dispatchEvent(
                new Event('input', { bubbles: true })
            );

            element.dispatchEvent(
                new Event('change', { bubbles: true })
            );
            """,
            start_date,
            "2026-10-01",
        )

        # Set end date through the DOM and fire normal browser events.
        self.driver.execute_script(
            """
            const element = arguments[0];
            const value = arguments[1];

            const setter = Object.getOwnPropertyDescriptor(
                HTMLInputElement.prototype,
                'value'
            ).set;

            setter.call(element, value);

            element.dispatchEvent(
                new Event('input', { bubbles: true })
            );

            element.dispatchEvent(
                new Event('change', { bubbles: true })
            );
            """,
            end_date,
            "2026-10-03",
        )

        reason.send_keys(
            "Selenium integration test"
        )

        submit_button = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    '#leaveForm button[type="submit"]',
                )
            )
        )

        submit_button.click()

        # Wait for the application to report a successful submission.
        alert = self.wait.until(
            EC.visibility_of_element_located(
                (By.ID, "leaveAlert")
            )
        )

        self.assertIn(
            "Leave request submitted successfully",
            alert.text,
        )

        # Open the employee's "My requests" page.
        my_requests_button = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    "#nav button:nth-child(3)",
                )
            )
        )
        my_requests_button.click()

        # The submitted request appears on the My requests page.
        # The UI renders PENDING_HR as "PENDING HR".
        self.wait.until(
            lambda driver: (
                "PENDING HR"
                in driver.find_element(
                    By.TAG_NAME,
                    "body",
                ).text
            )
        )

        body_text = self.driver.find_element(
            By.TAG_NAME,
            "body",
        ).text

        self.assertIn(
            "PENDING HR",
            body_text,
        )

        self.assertIn(
            "Selenium integration test",
            body_text,
        )


if __name__ == "__main__":
    unittest.main()
