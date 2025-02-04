# src/agent/http_client.py
import httpx
import asyncio
import time
from typing import Dict, List, Optional, AsyncGenerator
from queue import Queue
from logger import logger

class HTTPClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        token_url: str,
        max_retries: int = 3,
        timeout: int = 10,
        max_queue_size: int = 100,
    ):
        """
        初始化 HTTPClient。
        :param api_key: 用于获取 access_token 的 API 密钥。
        :param base_url: API 的基础 URL。
        :param token_url: 获取 access_token 的 URL。
        :param max_retries: 最大重试次数。
        :param timeout: 请求超时时间（秒）。
        :param max_queue_size: 请求队列的最大大小。
        """
        self.api_key = api_key
        self.base_url = base_url
        self.token_url = token_url
        self.max_retries = max_retries
        self.timeout = timeout
        self.max_queue_size = max_queue_size
        self.access_token = None
        self.token_expires_at = 0  # token 过期时间戳
        self.request_queue = Queue(maxsize=max_queue_size)  # 请求队列
        self.client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self._process_queue())  # 启动队列处理任务

    async def _get_access_token(self) -> str:
        """
        获取 access_token。如果当前 token 未过期，则直接返回；否则刷新 token。
        """
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        # 调用 API 获取新的 access_token
        retries = 0
        while retries < self.max_retries:
            try:
                response = await self.client.post(
                    self.token_url,  # 这里使用完整的 URL
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
                    await asyncio.sleep(1)  # 等待 1 秒后重试
            except Exception as e:
                logger.error(f"Failed to refresh access token (unexpected error): {e}")
                retries += 1
                if retries < self.max_retries:
                    await asyncio.sleep(1)  # 等待 1 秒后重试

        raise RuntimeError("Failed to refresh access token after maximum retries.")

    async def _get_headers(self) -> Dict[str, str]:
        """
        获取请求头，包括动态刷新的 access_token。
        """
        access_token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        发送 HTTP 请求，支持重试机制。
        """
        retries = 0
        while retries < self.max_retries:
            try:
                headers = await self._get_headers()
                response = await self.client.request(
                    method,
                    endpoint,  # 这里只需要传递路径部分
                    headers=headers,
                    **kwargs
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP request failed (HTTP error): {e}")
                retries += 1
                if retries < self.max_retries:
                    await asyncio.sleep(1)  # 等待 1 秒后重试
            except httpx.TimeoutError as e:
                logger.error(f"HTTP request timed out: {e}")
                retries += 1
                if retries < self.max_retries:
                    await asyncio.sleep(1)  # 等待 1 秒后重试
            except Exception as e:
                logger.error(f"HTTP request failed (unexpected error): {e}")
                retries += 1
                if retries < self.max_retries:
                    await asyncio.sleep(1)  # 等待 1 秒后重试

        raise RuntimeError("HTTP request failed after maximum retries.")

    async def _process_queue(self):
        """
        处理请求队列中的任务。
        """
        while True:
            if not self.request_queue.empty():
                method, endpoint, future, kwargs = self.request_queue.get()
                try:
                    result = await self._make_request(method, endpoint, **kwargs)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                finally:
                    self.request_queue.task_done()
            else:
                await asyncio.sleep(0.1)  # 队列为空时，短暂休眠

    async def enqueue_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        将请求加入队列，并返回 Future 对象。
        """
        future = self.loop.create_future()
        await self.request_queue.put((method, endpoint, future, kwargs))
        return await future

    async def chat_completions_create(
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

        return await self.enqueue_request(
            method="POST",
            endpoint="/v1/chat/completions",  # 这里只需要传递路径部分
            json=data
        )

    async def close(self):
        """
        关闭 HTTP 客户端。
        """
        await self.client.aclose()
