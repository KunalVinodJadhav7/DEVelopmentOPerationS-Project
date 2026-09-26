import os
import unittest
import uuid
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select


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

    def _register_user_and_login(self, username, email, password, role, expected_path):
        """Register a user for the requested role and sign in."""

        self.driver.get(f"{BASE_URL}/dashboard")

        # Open Create Account tab.
        self.wait_click(".tabs button:nth-child(2)")

        username_input = self.wait.until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, '#registerForm input[name="username"]')
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
        role_input = self.driver.find_element(
            By.CSS_SELECTOR,
            '#registerForm select[name="role"]',
        )

        username_input.clear()
        username_input.send_keys(username)

        email_input.clear()
        email_input.send_keys(email)

        password_input.clear()
        password_input.send_keys(password)

        Select(role_input).select_by_value(role)

        self.driver.find_element(
            By.CSS_SELECTOR,
            "#registerForm button",
        ).click()

        auth_alert = self.wait.until(
            EC.visibility_of_element_located((By.ID, "authAlert"))
        )

        registration_message = auth_alert.text.strip()

        self.assertIn(
            "Account created",
            registration_message,
            f"Registration failed for role {role!r}: {registration_message!r}",
        )

        # The application automatically switches back to Login and
        # pre-fills the newly registered username.
        login_username = self.wait.until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, '#loginForm input[name="username"]')
            )
        )
        login_password = self.driver.find_element(
            By.CSS_SELECTOR,
            '#loginForm input[name="password"]',
        )

        login_username.clear()
        login_username.send_keys(username)
        login_password.clear()
        login_password.send_keys(password)

        self.driver.find_element(
            By.CSS_SELECTOR,
            "#loginForm button",
        ).click()

        def login_finished(driver):
            if expected_path in driver.current_url:
                return True

            alert = driver.find_element(By.ID, "authAlert")
            alert_text = alert.text.strip()

            if not alert_text or alert_text == registration_message:
                return False

            return f"Login failed: {alert_text}"

        result = self.wait.until(login_finished)

        self.assertIs(
            result,
            True,
            f"{role.title()} login failed for {username!r}: "
            f"current_url={self.driver.current_url!r}",
        )

    def _submit_leave_request(self, reason_text):
        """Submit a leave request for the currently logged-in employee."""

        start_date = self.driver.find_element(By.NAME, "start_date")
        end_date = self.driver.find_element(By.NAME, "end_date")
        reason = self.driver.find_element(By.NAME, "reason")

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

        self.driver.execute_script(
            """
            const element = arguments[0];
            const value = arguments[1];
            const setter = Object.getOwnPropertyDescriptor(
                HTMLInputElement.prototype,
                'value'
            ).set;
            setter.call(element, value);
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            start_date,
            "2026-10-01",
        )

        self.driver.execute_script(
            """
            const element = arguments[0];
            const value = arguments[1];
            const setter = Object.getOwnPropertyDescriptor(
                HTMLInputElement.prototype,
                'value'
            ).set;
            setter.call(element, value);
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            end_date,
            "2026-10-03",
        )

        reason.send_keys(reason_text)

        submit_button = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    '#leaveForm button[type="submit"]',
                )
            )
        )
        submit_button.click()

        alert = self.wait.until(
            EC.visibility_of_element_located((By.ID, "leaveAlert"))
        )

        self.assertIn(
            "Leave request submitted successfully",
            alert.text,
        )

    def _create_employee_request(self, reason_text):
        """Register an employee and create a PENDING_HR leave request."""

        employee_username = f"hrflow_emp_{uuid.uuid4().hex[:8]}"
        employee_email = f"{employee_username}@example.com"
        employee_password = "Passw0rd!"

        self._register_user_and_login(
            employee_username,
            employee_email,
            employee_password,
            "employee",
            "/employee",
        )

        self._submit_leave_request(reason_text)

        # Confirm the request appears under My requests as PENDING HR.
        self.wait_click("#nav button:nth-child(3)")
        self.wait.until(
            lambda driver: (
                reason_text in driver.find_element(By.TAG_NAME, "body").text
                and "PENDING HR" in driver.find_element(By.TAG_NAME, "body").text
            )
        )

        return employee_username

    def _logout(self):
        """Log out through the application UI."""

        self.wait.until(
            EC.element_to_be_clickable((By.ID, "logout"))
        ).click()

        self.wait.until(
            lambda driver: "/dashboard" in driver.current_url
        )

    def _hr_decide(self, reason_text, approved):
        """Log in as HR, review a specific request, and record a decision."""

        hr_username = f"hr_{uuid.uuid4().hex[:8]}"
        hr_email = f"{hr_username}@example.com"
        hr_password = "Passw0rd!"

        self._register_user_and_login(
            hr_username,
            hr_email,
            hr_password,
            "hr",
            "/hr",
        )

        self.assertIn("/hr", self.driver.current_url)

        # HR review queue is the default page. Locate the exact request
        # by its unique Selenium-generated reason.
        request_card = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//article[contains(@class,'request')]"
                    f"[contains(.//div[contains(@class,'request-meta')], '{reason_text}')]",
                )
            )
        )

        review_button = request_card.find_element(
            By.XPATH,
            ".//button[normalize-space()='Review']",
        )
        self.wait.until(lambda driver: review_button.is_enabled())
        review_button.click()

        comments = self.wait.until(
            EC.visibility_of_element_located((By.ID, "reviewComments"))
        )
        comments.send_keys(
            "Selenium HR approval test decision."
            if approved
            else "Selenium HR rejection test decision."
        )

        if approved:
            decision_text = "Decision recorded"
            button_locator = (
                By.XPATH,
                "//button[normalize-space()='Approve']",
            )
        else:
            decision_text = "Request rejected"
            button_locator = (
                By.XPATH,
                "//button[normalize-space()='Reject']",
            )

        self.wait.until(
            EC.element_to_be_clickable(button_locator)
        ).click()

        # The modal is closed after the API call and the queue is refreshed.
        self.wait.until(
            EC.invisibility_of_element_located((By.ID, "reviewComments"))
        )

        # Verify the decision toast and then check the updated status
        # on the Audit Trail page, which shows all employee requests.
        self.wait.until(
            lambda driver: decision_text in driver.find_element(By.TAG_NAME, "body").text
        )

        self.wait_click("#nav button:nth-child(3)")

        expected_status = "PENDING MANAGER" if approved else "REJECTED"
        self.wait.until(
            lambda driver: (
                reason_text in driver.find_element(By.TAG_NAME, "body").text
                and expected_status in driver.find_element(By.TAG_NAME, "body").text
            )
        )

        body_text = self.driver.find_element(By.TAG_NAME, "body").text
        self.assertIn(reason_text, body_text)
        self.assertIn(expected_status, body_text)

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
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
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
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            end_date,
            "2026-10-03",
        )

        reason.send_keys("Selenium integration test")

        submit_button = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    '#leaveForm button[type="submit"]',
                )
            )
        )

        submit_button.click()

        alert = self.wait.until(
            EC.visibility_of_element_located((By.ID, "leaveAlert"))
        )

        self.assertIn(
            "Leave request submitted successfully",
            alert.text,
        )

        self.wait_click("#nav button:nth-child(3)")

        self.wait.until(
            lambda driver: (
                "PENDING HR"
                in driver.find_element(By.TAG_NAME, "body").text
            )
        )

        body_text = self.driver.find_element(
            By.TAG_NAME,
            "body",
        ).text

        self.assertIn("PENDING HR", body_text)
        self.assertIn("Selenium integration test", body_text)

    def test_hr_approves_employee_leave_request(self):
        """Verify HR can review and approve an employee leave request."""

        reason_text = f"Selenium HR approval {uuid.uuid4().hex[:8]}"

        self._create_employee_request(reason_text)
        self._logout()
        self._hr_decide(reason_text, approved=True)

    def test_hr_rejects_employee_leave_request(self):
        """Verify HR can review and reject an employee leave request."""

        reason_text = f"Selenium HR rejection {uuid.uuid4().hex[:8]}"

        self._create_employee_request(reason_text)
        self._logout()
        self._hr_decide(reason_text, approved=False)


    # ============================================================
    # WEEK 10 EXTENSIONS
    # Employee -> HR -> Manager -> Admin -> Super Admin -> Employee
    # ============================================================

    def _manager_decide(self, reason_text, approved):
        """Log in as Manager, review the request, and record a decision."""

        manager_username = f"manager_{uuid.uuid4().hex[:8]}"
        manager_email = f"{manager_username}@example.com"
        manager_password = "Passw0rd!"

        self._register_user_and_login(
            manager_username,
            manager_email,
            manager_password,
            "manager",
            "/manager",
        )

        self.assertIn(
            "/manager",
            self.driver.current_url,
        )

        # Manager queue is the second navigation button.
        self.wait_click("#nav button:nth-child(2)")

        request_card = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//article[contains(@class,'request')]"
                    f"[contains(.//div[contains(@class,'request-meta')], '{reason_text}')]",
                )
            )
        )

        review_button = request_card.find_element(
            By.XPATH,
            ".//button[normalize-space()='Review']",
        )

        self.wait.until(
            lambda driver: review_button.is_enabled()
        )
        review_button.click()

        comments = self.wait.until(
            EC.visibility_of_element_located(
                (By.ID, "reviewComments")
            )
        )

        comments.send_keys(
            "Selenium Manager approval test decision."
            if approved
            else "Selenium Manager rejection test decision."
        )

        if approved:
            decision_text = "Decision recorded"
            button_locator = (
                By.XPATH,
                "//button[normalize-space()='Approve']",
            )
        else:
            decision_text = "Request rejected"
            button_locator = (
                By.XPATH,
                "//button[normalize-space()='Reject']",
            )

        self.wait.until(
            EC.element_to_be_clickable(button_locator)
        ).click()

        # The modal closes after the API call.
        self.wait.until(
            EC.invisibility_of_element_located(
                (By.ID, "reviewComments")
            )
        )

        self.wait.until(
            lambda driver: (
                decision_text
                in driver.find_element(
                    By.TAG_NAME,
                    "body",
                ).text
            )
        )

        # Audit Trail is the third navigation button and shows request
        # status/history for this role.
        self.wait_click("#nav button:nth-child(3)")

        expected_status = (
            "PENDING ADMIN"
            if approved
            else "REJECTED"
        )

        self.wait.until(
            lambda driver: (
                reason_text
                in driver.find_element(
                    By.TAG_NAME,
                    "body",
                ).text
                and expected_status
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
            reason_text,
            body_text,
        )

        self.assertIn(
            expected_status,
            body_text,
        )

    def _admin_decide(self, reason_text, approved):
        """Log in as Admin, finalize the request, and record a decision."""

        admin_username = f"admin_{uuid.uuid4().hex[:8]}"
        admin_email = f"{admin_username}@example.com"
        admin_password = "Passw0rd!"

        self._register_user_and_login(
            admin_username,
            admin_email,
            admin_password,
            "admin",
            "/admin",
        )

        self.assertIn(
            "/admin",
            self.driver.current_url,
        )

        # Admin queue is the second navigation button.
        self.wait_click("#nav button:nth-child(2)")

        request_card = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//article[contains(@class,'request')]"
                    f"[contains(.//div[contains(@class,'request-meta')], '{reason_text}')]",
                )
            )
        )

        self.assertIn(
            "PENDING ADMIN",
            request_card.text.upper(),
        )

        finalize_button = request_card.find_element(
            By.XPATH,
            ".//button[normalize-space()='Finalize']",
        )

        self.wait.until(
            lambda driver: finalize_button.is_enabled()
        )
        finalize_button.click()

        comments = self.wait.until(
            EC.visibility_of_element_located(
                (By.ID, "reviewComments")
            )
        )

        comments.send_keys(
            "Selenium Admin finalization approval."
            if approved
            else "Selenium Admin finalization rejection."
        )

        if approved:
            decision_text = "Decision recorded"
            button_locator = (
                By.XPATH,
                "//button[normalize-space()='Approve']",
            )
        else:
            decision_text = "Request rejected"
            button_locator = (
                By.XPATH,
                "//button[normalize-space()='Reject']",
            )

        self.wait.until(
            EC.element_to_be_clickable(button_locator)
        ).click()

        self.wait.until(
            EC.invisibility_of_element_located(
                (By.ID, "reviewComments")
            )
        )

        self.wait.until(
            lambda driver: (
                decision_text
                in driver.find_element(
                    By.TAG_NAME,
                    "body",
                ).text
            )
        )

        expected_status = (
            "APPROVED"
            if approved
            else "REJECTED"
        )

        # Verify through Audit Trail.
        self.wait_click("#nav button:nth-child(3)")

        self.wait.until(
            lambda driver: (
                reason_text
                in driver.find_element(
                    By.TAG_NAME,
                    "body",
                ).text
                and expected_status
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
            reason_text,
            body_text,
        )

        self.assertIn(
            expected_status,
            body_text,
        )

    def _super_admin_notify(self, reason_text, expected_status):
        """Log in as Super Admin and notify the employee."""

        super_admin_username = (
            f"superadmin_{uuid.uuid4().hex[:8]}"
        )
        super_admin_email = (
            f"{super_admin_username}@example.com"
        )
        super_admin_password = "Passw0rd!"

        self._register_user_and_login(
            super_admin_username,
            super_admin_email,
            super_admin_password,
            "super_admin",
            "/super-admin",
        )

        self.assertIn(
            "/super-admin",
            self.driver.current_url,
        )

        # Super Admin Operations is the second navigation button.
        self.wait_click("#nav button:nth-child(2)")

        request_card = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//article[contains(@class,'request')]"
                    f"[contains(.//div[contains(@class,'request-meta')], '{reason_text}')]",
                )
            )
        )

        self.assertIn(
            expected_status,
            request_card.text.upper(),
        )

        notify_button = request_card.find_element(
            By.XPATH,
            ".//button[normalize-space()='Notify']",
        )

        self.wait.until(
            lambda driver: notify_button.is_enabled()
        )
        notify_button.click()

        # Current frontend shows this toast after notification succeeds.
        self.wait.until(
            lambda driver: (
                "Employee notified for leave #"
                in driver.find_element(
                    By.ID,
                    "toast",
                ).text
            )
        )

        toast_text = self.driver.find_element(
            By.ID,
            "toast",
        ).text

        self.assertIn(
            "Employee notified for leave #",
            toast_text,
        )

        # Open Audit Trail and inspect the request audit.
        self.wait_click("#nav button:nth-child(3)")

        self.wait.until(
            lambda driver: (
                reason_text
                in driver.find_element(
                    By.TAG_NAME,
                    "body",
                ).text
            )
        )

        audit_request_card = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//article[contains(@class,'request')]"
                    f"[contains(.//div[contains(@class,'request-meta')], '{reason_text}')]",
                )
            )
        )

        view_button = audit_request_card.find_element(
            By.XPATH,
            ".//button[normalize-space()='View']",
        )

        self.wait.until(
            lambda driver: view_button.is_enabled()
        )
        view_button.click()

        modal_audit = self.wait.until(
            EC.visibility_of_element_located(
                (By.ID, "modalAudit")
            )
        )

        audit_text = modal_audit.text

        self.assertTrue(
            any(
                token in audit_text.lower()
                for token in (
                    "notif",
                    "notify",
                    "notified",
                )
            ),
            (
                "Notification action was not found in the "
                f"request audit trail.\n{audit_text}"
            ),
        )

        return toast_text


    def _login_existing_user(
        self,
        username,
        password,
        expected_path="/employee",
    ):
        """Log in an already-registered user through the real dashboard UI."""

        self.driver.get(
            f"{BASE_URL}/dashboard"
        )

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

        login_username.clear()
        login_username.send_keys(username)

        login_password.clear()
        login_password.send_keys(password)

        self.driver.find_element(
            By.CSS_SELECTOR,
            "#loginForm button",
        ).click()

        def login_finished(driver):
            if expected_path in driver.current_url:
                return True

            try:
                alert_text = driver.find_element(
                    By.ID,
                    "authAlert",
                ).text.strip()
            except Exception:
                return False

            if not alert_text:
                return False

            return f"Login failed: {alert_text}"

        result = self.wait.until(login_finished)

        self.assertIs(
            result,
            True,
            f"Existing-user login failed for {username!r}. "
            f"Current URL: {self.driver.current_url!r}",
        )

    def _verify_employee_final_status(
        self,
        employee_username,
        employee_email,
        employee_password,
        reason_text,
        expected_status,
    ):
        """Log the employee back in and verify final status + notification."""

        self._login_existing_user(
            employee_username,
            employee_password,
            expected_path="/employee",
        )

        self.assertIn(
            "/employee",
            self.driver.current_url,
        )

        # Employee queue is the third navigation button.
        self.wait_click("#nav button:nth-child(3)")

        request_card = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//article[contains(@class,'request')]"
                    f"[contains(.//div[contains(@class,'request-meta')], '{reason_text}')]",
                )
            )
        )

        self.assertIn(
            expected_status,
            request_card.text.upper(),
        )

        # Open the request and inspect its audit trail.
        view_button = request_card.find_element(
            By.XPATH,
            ".//button[normalize-space()='View']",
        )

        self.wait.until(
            lambda driver: view_button.is_enabled()
        )
        view_button.click()

        modal_audit = self.wait.until(
            EC.visibility_of_element_located(
                (By.ID, "modalAudit")
            )
        )

        audit_text = modal_audit.text

        self.assertTrue(
            any(
                token in audit_text.lower()
                for token in (
                    "notif",
                    "notify",
                    "notified",
                )
            ),
            (
                "Employee could see the final status, but the "
                "notification event was not visible in the audit trail.\n"
                f"{audit_text}"
            ),
        )

        return audit_text

    def _run_week10_complete_workflow(
        self,
        suffix,
        admin_approved,
    ):
        """
        Full Week 10 acceptance flow:

        Employee -> Submit -> HR Approve -> Manager Approve
        -> Admin Finalize -> Super Admin Notify -> Employee Verify.
        """

        employee_username = (
            f"week10_emp_{suffix}_{uuid.uuid4().hex[:8]}"
        )
        employee_email = (
            f"{employee_username}@example.com"
        )
        employee_password = "Passw0rd!"

        reason_text = (
            f"Selenium Week 10 {suffix} "
            f"{uuid.uuid4().hex[:8]}"
        )

        # --------------------------------------------------------
        # 1. Employee registers and submits leave request.
        # --------------------------------------------------------
        self._register_user_and_login(
            employee_username,
            employee_email,
            employee_password,
            "employee",
            "/employee",
        )

        self.assertIn(
            "/employee",
            self.driver.current_url,
        )

        self._submit_leave_request(
            reason_text
        )

        # Verify initial state.
        self.wait_click("#nav button:nth-child(3)")

        self.wait.until(
            lambda driver: (
                reason_text
                in driver.find_element(
                    By.TAG_NAME,
                    "body",
                ).text
                and "PENDING HR"
                in driver.find_element(
                    By.TAG_NAME,
                    "body",
                ).text
            )
        )

        # --------------------------------------------------------
        # 2. HR reviews and approves.
        # --------------------------------------------------------
        self._logout()
        self._hr_decide(
            reason_text,
            approved=True,
        )

        # --------------------------------------------------------
        # 3. Manager reviews and approves.
        # --------------------------------------------------------
        self._logout()
        self._manager_decide(
            reason_text,
            approved=True,
        )

        # --------------------------------------------------------
        # 4. Admin finalizes.
        # --------------------------------------------------------
        self._logout()
        self._admin_decide(
            reason_text,
            approved=admin_approved,
        )

        expected_status = (
            "APPROVED"
            if admin_approved
            else "REJECTED"
        )

        # --------------------------------------------------------
        # 5. Super Admin notifies employee.
        # --------------------------------------------------------
        self._logout()

        toast_text = self._super_admin_notify(
            reason_text,
            expected_status,
        )

        self.assertIn(
            "Employee notified for leave #",
            toast_text,
        )

        # --------------------------------------------------------
        # 6. Employee sees final status and notification audit.
        # --------------------------------------------------------
        self._logout()

        self._verify_employee_final_status(
            employee_username,
            employee_email,
            employee_password,
            reason_text,
            expected_status,
        )

    def test_week10_complete_approval_workflow(self):
        """Complete Week 10 approval path through employee notification."""

        self._run_week10_complete_workflow(
            suffix="approval",
            admin_approved=True,
        )

    def test_week10_complete_rejection_workflow(self):
        """Complete Week 10 rejection path through employee notification."""

        self._run_week10_complete_workflow(
            suffix="rejection",
            admin_approved=False,
        )


if __name__ == "__main__":
    unittest.main()
