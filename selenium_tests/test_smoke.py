from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def test_application_opens(driver, base_url):
    """Verify that the employee leave application opens successfully."""

    driver.get(base_url)

    wait = WebDriverWait(driver, 10)

    wait.until(
        EC.presence_of_element_located(
            (By.TAG_NAME, "body")
        )
    )

    assert driver.current_url.startswith(base_url)

    body_text = driver.find_element(
        By.TAG_NAME,
        "body"
    ).text.strip()

    assert body_text, "Application page contains no visible body text"

    print(f"Application URL: {driver.current_url}")
    print(f"Page title: {driver.title}")


def test_application_ui_inventory(driver, base_url):
    """
    Record the current application's links, buttons, forms and inputs.

    This gives us the exact UI structure needed for the workflow tests.
    """

    driver.get(base_url)

    wait = WebDriverWait(driver, 10)

    wait.until(
        EC.presence_of_element_located(
            (By.TAG_NAME, "body")
        )
    )

    # Capture body text for diagnostics if the UI contains no controls.
    body_text = driver.find_element(
        By.TAG_NAME,
        "body"
    ).text.strip()

    links = driver.find_elements(By.TAG_NAME, "a")
    buttons = driver.find_elements(By.TAG_NAME, "button")
    inputs = driver.find_elements(By.TAG_NAME, "input")
    textareas = driver.find_elements(By.TAG_NAME, "textarea")
    selects = driver.find_elements(By.TAG_NAME, "select")
    forms = driver.find_elements(By.TAG_NAME, "form")

    output = []

    output.append(f"URL: {driver.current_url}")
    output.append(f"TITLE: {driver.title}")
    output.append("")

    output.append("LINKS")
    output.append("-----")

    for element in links:
        output.append(
            f"text={element.text!r} "
            f"href={element.get_attribute('href')!r}"
        )

    output.append("")
    output.append("BUTTONS")
    output.append("-------")

    for element in buttons:
        output.append(
            f"text={element.text!r} "
            f"id={element.get_attribute('id')!r} "
            f"name={element.get_attribute('name')!r} "
            f"type={element.get_attribute('type')!r}"
        )

    output.append("")
    output.append("INPUTS")
    output.append("------")

    for element in inputs:
        output.append(
            f"type={element.get_attribute('type')!r} "
            f"id={element.get_attribute('id')!r} "
            f"name={element.get_attribute('name')!r} "
            f"value={element.get_attribute('value')!r} "
            f"placeholder={element.get_attribute('placeholder')!r}"
        )

    output.append("")
    output.append("TEXTAREAS")
    output.append("---------")

    for element in textareas:
        output.append(
            f"id={element.get_attribute('id')!r} "
            f"name={element.get_attribute('name')!r} "
            f"placeholder={element.get_attribute('placeholder')!r}"
        )

    output.append("")
    output.append("SELECTS")
    output.append("-------")

    for element in selects:
        output.append(
            f"id={element.get_attribute('id')!r} "
            f"name={element.get_attribute('name')!r}"
        )

    output.append("")
    output.append(f"FORMS: {len(forms)}")

    inventory_file = (
        Path(__file__).resolve().parent
        / "artifacts"
        / "logs"
        / "ui_inventory.txt"
    )

    inventory_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    inventory_file.write_text(
        "\n".join(output),
        encoding="utf-8",
    )

    # Basic application-level assertions.
    assert (
        len(links)
        + len(buttons)
        + len(inputs)
        + len(textareas)
        + len(selects)
        + len(forms)
    ) > 0, (
        f"No usable UI controls found at {driver.current_url}. "
        f"Title={driver.title!r}, Body={body_text[:300]!r}"
    )