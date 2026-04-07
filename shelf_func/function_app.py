import azure.functions as func
import logging
import json
import os
import uuid
import datetime
import requests
from azure.identity import ManagedIdentityCredential
from azure.cosmos import CosmosClient

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# ── helpers ─────────────────────────────────────────────────────────────────
def _normalize_result(result):
    """Convert AML string payloads into JSON objects before persisting."""
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"raw_result": result}
    return result


def _call_aml(image_bytes: bytes, blob_name: str) -> dict:
    """Call AML Online Endpoint for shelf detection inference."""
    endpoint_url = os.environ["AML_ENDPOINT_URL"]
    api_key      = os.environ.get("AML_API_KEY", "")

    payload = {
        "input_data": {
            "blob_name": blob_name,
            "image_b64": __import__("base64").b64encode(image_bytes).decode()
        }
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    resp = requests.post(endpoint_url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _save_to_cosmos(result: dict, blob_name: str) -> None:
    """Persist detection result to Cosmos DB using Managed Identity (disableLocalAuth=true)."""
    cosmos_uri = os.environ["COSMOS_URI"]
    database_name = os.environ.get("COSMOS_DATABASE_NAME", "ShelfVisionDB")
    container_name = os.environ.get("COSMOS_CONTAINER_NAME", "DetectionResults")
    # Always use managed identity — Cosmos DB has disableLocalAuth=true (key auth disabled)
    client = CosmosClient(cosmos_uri, credential=ManagedIdentityCredential())

    container = client.get_database_client(database_name).get_container_client(container_name)
    normalized_result = _normalize_result(result)

    doc = {
        "id": str(uuid.uuid4()),
        "storeId": os.environ.get("STORE_ID", "store-mvp-001"),
        "blobName": blob_name,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "result": normalized_result,
    }
    container.upsert_item(doc)
    logging.info("Saved result to Cosmos DB: id=%s", doc["id"])


# ── health check ─────────────────────────────────────────────────────────────
@app.route(route="health")
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Health check called")
    return func.HttpResponse("OK - service is running", status_code=200)


# ── trigger ──────────────────────────────────────────────────────────────────
@app.blob_trigger(
    arg_name="myblob",
    path="raw-images/{name}",
    connection="AzureWebJobsStorage",
)
def shelf_detection_trigger(myblob: func.InputStream):
    blob_name = myblob.name
    logging.info("Blob trigger fired: name=%s, size=%d bytes", blob_name, myblob.length)

    image_bytes = myblob.read()

    try:
        result = _call_aml(image_bytes, blob_name)
        logging.info("AML inference result: %s", json.dumps(result)[:200])
    except Exception as exc:
        logging.error("AML call failed: %s", exc)
        result = {"error": str(exc), "blob_name": blob_name}

    _save_to_cosmos(result, blob_name)
    logging.info("Processing complete for blob: %s", blob_name)
