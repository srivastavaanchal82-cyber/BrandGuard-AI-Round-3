import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))
from app import main
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
BRAND = dict(brand_name="ABC Technologies", prohibited_words="cheapest", approved_claims="")

def test_prevent_example_and_review(monkeypatch):
    monkeypatch.setattr(
    main,
    "gemini_findings",
    lambda *args: ([], "Gemini disabled in unit test")
)
    assert c.put("/api/brand/default", json=BRAND).status_code == 200
    r = c.post("/api/prevent/analyse", json={"text": "ABC Tech is the cheapest company in India. We guarantee 100% results!"}).json()
    cats = {f["category"] for f in r["findings"]}
    assert cats == {"Incorrect brand name", "Unsupported superlative", "Unsupported guarantee"}
    assert c.post("/api/reviews", json={"analysis_id": r["id"], "decision": "Approved"}).status_code == 200
    s = c.get("/api/stats").json(); assert s["approved"] == 1 and s["issues"] == 3
    assert c.get("/api/reviews").json()[0]["decision"] == "Approved"

def test_no_brand_is_404_and_campaign():
    assert c.get("/api/brand/none").status_code == 404
    r = c.post("/api/protect/campaign-compare", json=dict(approved_discount="20%", observed_discount="80%", approved_website="nova.com", observed_website="https://nova-deals.xyz/x")).json()
    assert [f["mismatch_type"] for f in r["findings"]] == ["Discount mismatch", "Unapproved website"]
    ok = c.post("/api/protect/campaign-compare", json=dict(approved_discount="20%", observed_discount="20 %", approved_website="nova.com", observed_website="shop.nova.com")).json()
    assert ok["findings"] == []
