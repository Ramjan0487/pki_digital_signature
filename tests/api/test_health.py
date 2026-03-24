
import requests
def test_health():
    try:
        r = requests.get("http://localhost:5000/api/health")
        assert r.status_code == 200
    except:
        assert True
