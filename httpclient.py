# src/agent/http_client.py
import httpx
import time
from typing import Dict, List, Optional
from logger import logger

class HTTPClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        token_url: str,
        max_retries: int = 3,
        timeout: int = 10,
    ):
        """
        初始化 HTTPClient。
        :param api_key: 用于获取 access_token 的 API 密钥。
        :param base_url: API 的基础 URL。
        :param token_url: 获取 access_token 的 URL。
        :param max_retries: 最大重试次数。
        :param timeout: 请求超时时间（秒）。
        """
        self.api_key = api_key
        self.base_url = base_url
        self.token_url = token_url
        self.max_retries = max_retries
        self.timeout = timeout
        self.access_token = None
        self.token_expires_at = 0  # token 过期时间戳
        self.client = httpx.Client(base_url=base_url, timeout=timeout)

    def _get_access_token(self) -> str:
        """
        获取 access_token。如果当前 token 未过期，则直接返回；否则刷新 token。
        """
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        # 调用 API 获取新的 access_token
        retries = 0
        while retries < self.max_retries:
            try:
                response = self.client.post(
                    self.token_url,
                    json={"api_key": self.api_key},
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                token_data = response.json()
                self.access_token = token_data["access_token"]
                self.token_expires_at = time.time() + token_data["expires_in"]  # 设置过期时间
                logger.debug("Successfully refreshed access token.")
                return self.access_token
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to refresh access token (HTTP error): {e}")
                retries += 1
                if retries < self.max_retries:
                    time.sleep(1)  # 等待 1 秒后重试
            except Exception as e:
                logger.error(f"Failed to refresh access token (unexpected error): {e}")
                retries += 1
                if retries < self.max_retries:
                    time.sleep(1)  # 等待 1 秒后重试

        raise RuntimeError("Failed to refresh access token after maximum retries.")

    def _get_headers(self) -> Dict[str, str]:
        """
        获取请求头，包括动态刷新的 access_token。
        """
        access_token = self._get_access_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        发送 HTTP 请求，支持重试机制。
        """
        retries = 0
        while retries < self.max_retries:
            try:
                response = self.client.request(
                    method,
                    endpoint,
                    headers=self._get_headers(),
                    **kwargs
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP request failed (HTTP error): {e}")
                retries += 1
                if retries < self.max_retries:
                    time.sleep(1)  # 等待 1 秒后重试
            except httpx.TimeoutError as e:
                logger.error(f"HTTP request timed out: {e}")
                retries += 1
                if retries < self.max_retries:
                    time.sleep(1)  # 等待 1 秒后重试
            except Exception as e:
                logger.error(f"HTTP request failed (unexpected error): {e}")
                retries += 1
                if retries < self.max_retries:
                    time.sleep(1)  # 等待 1 秒后重试

        raise RuntimeError("HTTP request failed after maximum retries.")

    def chat_completions_create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs
    ) -> Dict:
        """
        发送聊天补全请求，接口与 OpenAI SDK 保持一致。
        """
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }

        return self._make_request(
            method="POST",
            endpoint="/v1/chat/completions",
            json=data
        )

    def close(self):
        """
        关闭 HTTP 客户端。
        """
        self.client.close()
