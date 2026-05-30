import csv
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import streamlit as st


CSV_PATH = Path(__file__).with_name("products.csv")
DEFAULT_ENRICH_URL = "http://localhost:8000/enrich"


def load_products(csv_path: Path = CSV_PATH) -> list[dict]:
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    products = []
    for row in rows:
        products.append(
            {
                "product_code": row["product_code"],
                "description": row["description"],
                "attributes": json.loads(row["attributes"]),
            }
        )
    return products


def build_enrichment_payload(product: dict, instructions: str) -> dict:
    return {
        "product_code": product["product_code"],
        "description": product["description"],
        "attributes": product["attributes"],
        "instructions": instructions,
    }


def call_enrich_endpoint(url: str, payload: dict, timeout: int = 30) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def format_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8")
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return f"Enrich endpoint failed with HTTP {exc.code}."

    detail = payload.get("detail")
    if isinstance(detail, str):
        return f"Enrich endpoint failed with HTTP {exc.code}: {detail}"

    return f"Enrich endpoint failed with HTTP {exc.code}."


def main() -> None:
    st.set_page_config(page_title="Product Enrichment", layout="centered")
    st.title("Product Enrichment")

    products = load_products()
    products_by_code = {product["product_code"]: product for product in products}

    selected_code = st.selectbox("Product code", list(products_by_code))
    selected_product = products_by_code[selected_code]

    st.subheader("Description")
    st.write(selected_product["description"])

    st.subheader("Attributes")
    st.json(selected_product["attributes"])

    instructions = st.text_area(
        "Values",
        placeholder="Write enrichment instructions or values here",
    )

    enrich_url = os.getenv("ENRICH_ENDPOINT_URL", DEFAULT_ENRICH_URL)
    timeout = int(os.getenv("ENRICH_TIMEOUT_SECONDS", "30"))

    if st.button("Enrich"):
        payload = build_enrichment_payload(selected_product, instructions)
        with st.spinner("Calling enrich endpoint..."):
            try:
                enriched_data = call_enrich_endpoint(enrich_url, payload, timeout)
            except urllib.error.HTTPError as exc:
                st.error(format_http_error(exc))
            except urllib.error.URLError as exc:
                st.error(f"Enrich endpoint failed: {exc}")
            except TimeoutError:
                st.error("Enrich endpoint timed out.")
            except json.JSONDecodeError:
                st.error("Enrich endpoint returned invalid JSON.")
            else:
                st.subheader("Enriched data")
                st.json(enriched_data)


if __name__ == "__main__":
    main()
