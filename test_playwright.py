from playwright.sync_api import sync_playwright

html = """
<!DOCTYPE html>
<html>
<head><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-blue-100 text-blue-900 p-10">
    <h1 class="text-4xl font-bold">Hello World</h1>
</body>
</html>
"""

def take_pdf():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(path="test.pdf", print_background=True)
        browser.close()

take_pdf()