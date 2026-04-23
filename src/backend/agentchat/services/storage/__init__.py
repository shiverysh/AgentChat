from typing import Any

from agentchat.services.storage.minio import MinioClient
from agentchat.services.storage.oss import OSSClient
from agentchat.settings import app_settings


def _build_storage_client():
    if not app_settings.storage:
        raise ValueError("存储服务尚未初始化配置。")

    if app_settings.storage.mode == "minio":
        return MinioClient()

    return OSSClient()


class LazyStorageClient:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = _build_storage_client()
        return self._client

    def __getattr__(self, item: str) -> Any:
        return getattr(self._get_client(), item)


storage_client = LazyStorageClient()

if __name__ == "__main__":
    storage_client.list_files_in_folder("icons/user/")
