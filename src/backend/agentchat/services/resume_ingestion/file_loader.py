import os
import tempfile
from urllib.parse import unquote, urlparse

import requests

from agentchat.services.storage import storage_client
from agentchat.settings import app_settings


def extract_object_name(file_url: str) -> str | None:
    parsed_file_url = urlparse(file_url)
    if not parsed_file_url.path:
        return None

    storage_base_url = getattr(app_settings.storage.active, "base_url", "")
    parsed_storage_url = urlparse(storage_base_url)

    if parsed_file_url.netloc and parsed_storage_url.netloc and parsed_file_url.netloc != parsed_storage_url.netloc:
        return None

    object_name = unquote(parsed_file_url.path).lstrip("/")
    base_path = parsed_storage_url.path.strip("/")
    bucket_name = getattr(app_settings.storage.active, "bucket_name", "").strip("/")

    if base_path and object_name.startswith(f"{base_path}/"):
        object_name = object_name[len(base_path) + 1:]

    if bucket_name and object_name.startswith(f"{bucket_name}/"):
        object_name = object_name[len(bucket_name) + 1:]

    return object_name or None


def extract_file_name(file_url: str) -> str:
    parsed_file_url = urlparse(file_url)
    file_name = os.path.basename(unquote(parsed_file_url.path))
    return file_name or "uploaded_resume"


def load_file_bytes(file_url: str, file_name: str | None = None) -> bytes:
    resolved_file_name = file_name or extract_file_name(file_url)
    object_name = extract_object_name(file_url)
    if object_name:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_file_path = os.path.join(temp_dir, resolved_file_name)
            storage_client.download_file(object_name, local_file_path)
            if os.path.exists(local_file_path):
                with open(local_file_path, "rb") as file:
                    return file.read()

    response = requests.get(file_url, timeout=20)
    response.raise_for_status()
    return response.content
