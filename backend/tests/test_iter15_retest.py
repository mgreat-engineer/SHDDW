# Shadow iteration-15 retest: passwords CSV import edge cases + import-chrome tolerant of odd helper results
# Run: pytest /app/backend/tests/test_iter15_retest.py -n 0 -v -s
import threading, time
import pytest, requests
import subprocess
from test_iter14_folders_import import A_EMAIL, upload, run_fake_helper, BASE_URL  # noqa: F401


@pytest.fixture(scope="module")
def A():
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + subprocess.check_output(["python", "/app/tests/clerk_token.py", A_EMAIL], text=True).strip()
    return s


class TestPasswordImportEdge:
    @pytest.mark.parametrize("content", [b"hello world\n", b"", b"foo,bar\n", b"\xef\xbb\xbf", b"   \n\n"])
    def test_bad_files_400(self, A, content):
        r = upload(A, content, name="x.txt")
        print(repr(content), r.status_code, r.text[:120])
        assert r.status_code == 400, r.text
        assert "detail" in r.json()

    def test_valid_header_only_ok(self, A):
        r = upload(A, b"name,url,username,password\n")
        assert r.status_code == 200 and r.json() == {"saved": 0, "skipped": 0}


class TestImportChromeOdd:
    @pytest.mark.parametrize("result,found", [(None, 0), ({"a": 1}, 0), ("str", 0),
                                              ([1, "x", None, ["y"], {"title": "TEST_o", "url": "https://example.com/TEST_chrome_odd", "folder": None}], 1)])
    def test_odd_results(self, A, result, found):
        code = A.post(f"{BASE_URL}/api/devices/pair-code").json()["code"]
        p = requests.post(f"{BASE_URL}/api/helper/pair", json={"code": code, "name": "TEST_iter15_fake"}).json()
        ready, stop = threading.Event(), threading.Event()
        ans = lambda m: {"result": result} if m == "chrome_bookmarks" else {"error": "TEST"}
        th = threading.Thread(target=run_fake_helper, args=(p["token"], ans, ready, stop), daemon=True)
        th.start()
        try:
            assert ready.wait(25)
            time.sleep(1.5)
            r = A.post(f"{BASE_URL}/api/bookmarks/import-chrome")
            print(repr(result)[:60], r.status_code, r.text[:200])
            assert r.status_code == 200, r.text
            assert r.json()["found"] == found
            if found:
                assert r.json()["added"] in (0, 1)
                bm = [b for b in A.get(f"{BASE_URL}/api/bookmarks").json() if b["url"] == "https://example.com/TEST_chrome_odd"]
                assert bm and bm[0]["folder"] == ""
        finally:
            stop.set(); th.join(10)
            A.delete(f"{BASE_URL}/api/devices/{p['device_id']}")
            for b in A.get(f"{BASE_URL}/api/bookmarks").json():
                if "TEST_chrome" in b["url"]:
                    A.delete(f"{BASE_URL}/api/bookmarks/{b['id']}")
        time.sleep(1)
        assert A.get(f"{BASE_URL}/api/target").json()["target"] == "cloud"
