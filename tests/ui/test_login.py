
from selenium import webdriver
def test_ui():
    driver = webdriver.Chrome()
    driver.get("http://localhost:5000/login")
    assert "Login" in driver.page_source
    driver.quit()
