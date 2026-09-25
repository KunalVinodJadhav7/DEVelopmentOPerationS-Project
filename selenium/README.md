# Selenium test suite

The executable Selenium tests live in `selenium_tests/` rather than `selenium/` because naming the Python test package `selenium` shadows the real Selenium WebDriver package during imports.

Run locally through Gradle:

```bash
gradle seleniumTest
```

Or directly:

```bash
python -m pytest selenium_tests -v
```

The CI runner stores JUnit XML in `test-results/selenium-junit.xml` and screenshots for failed tests under `test-results/screenshots/`.
