import json
import io
import urllib.error

from frontend.app import (
    build_enrichment_payload,
    call_enrich_endpoint,
    format_http_error,
    load_products,
)


def test_load_products_reads_frontend_csv():
    products = load_products()

    assert products[0] == {
        "product_code": "ELEC-001",
        "description": "Wireless Bluetooth Headphones with noise cancellation",
        "attributes": {
            "brand": "SoundMax",
            "color": "Black",
            "battery_life": "30h",
            "connectivity": "Bluetooth 5.3",
        },
    }


def test_build_enrichment_payload_matches_request_schema():
    product = {
        "product_code": "HOME-001",
        "description": "Stainless Steel Water Bottle 1L",
        "attributes": {"capacity": "1L"},
    }

    payload = build_enrichment_payload(product, "Make it marketplace ready")

    assert payload == {
        "product_code": "HOME-001",
        "description": "Stainless Steel Water Bottle 1L",
        "attributes": {"capacity": "1L"},
        "instructions": "Make it marketplace ready",
    }


def test_call_enrich_endpoint_posts_payload_and_returns_json(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "product_code": "APP-001",
                    "description": "Enriched shirt description",
                    "attributes": {"fit": "Regular", "material": "Cotton"},
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["content_type"] = request.headers["Content-type"]
        captured["method"] = request.method
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    response = call_enrich_endpoint(
        "http://localhost:8000/enrich",
        {
            "product_code": "APP-001",
            "description": "Men's Cotton Polo Shirt",
            "attributes": {"fit": "Regular"},
            "instructions": "Improve title",
        },
        timeout=5,
    )

    assert captured == {
        "url": "http://localhost:8000/enrich",
        "timeout": 5,
        "body": {
            "product_code": "APP-001",
            "description": "Men's Cotton Polo Shirt",
            "attributes": {"fit": "Regular"},
            "instructions": "Improve title",
        },
        "content_type": "application/json",
        "method": "POST",
    }
    assert response["description"] == "Enriched shirt description"


def test_format_http_error_shows_fastapi_detail():
    error = urllib.error.HTTPError(
        url="http://localhost:8000/enrich",
        code=502,
        msg="Bad Gateway",
        hdrs={},
        fp=io.BytesIO(b'{"detail":"LLM enrichment request failed."}'),
    )

    message = format_http_error(error)

    assert message == (
        "Enrich endpoint failed with HTTP 502: LLM enrichment request failed."
    )
