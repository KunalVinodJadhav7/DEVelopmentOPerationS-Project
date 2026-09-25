import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:18000')
pytest_report = Path(os.getenv('SELENIUM_JUNIT_REPORT', 'build/test-results/selenium-junit.xml'))
screenshot_dir = Path(os.getenv('SCREENSHOT_DIR', 'test-results/screenshots'))
log_file = Path('test-results/app.log')
pytest_report.parent.mkdir(parents=True, exist_ok=True)
screenshot_dir.mkdir(parents=True, exist_ok=True)


def wait_for_health(url, timeout=45):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f'{url}/health', timeout=3) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f'Application did not become healthy: {last_error}')


root = Path(__file__).resolve().parents[1]
env = os.environ.copy()
env['BASE_URL'] = BASE_URL
env.setdefault('SCREENSHOT_DIR', str(screenshot_dir.resolve()))

with log_file.open('w', encoding='utf-8') as log:
    app = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '18000'],
        cwd=root,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )

    try:
        wait_for_health(BASE_URL)
        command = [
            sys.executable,
            '-m',
            'pytest',
            'selenium_tests',
            '-q',
            f'--junitxml={pytest_report}',
        ]
        completed = subprocess.run(command, cwd=root, env=env)
        raise SystemExit(completed.returncode)
    finally:
        app.terminate()
        try:
            app.wait(timeout=10)
        except subprocess.TimeoutExpired:
            app.kill()
