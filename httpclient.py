# src/agent/http_client.py
import httpx
import asyncio
import time
from typing import Dict, List, Optional, AsyncGenerator
from asyncio import Queue as AsyncQueue
from logger import logger

class HTTPClient:
    TOKEN_REFRESH_THRESHOLD = 300  # 提前5分钟刷新token
    MAX_CONCURRENT_REQUESTS = 20   # 最大并发请求数
    BASE_RETRY_DELAY = 1.0        # 基础重试延迟时间（秒）

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
        self.request_queue = AsyncQueue(maxsize=max_queue_size)  # 使用异步队列
        self.client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._queue_processor_task = None  # 用于存储队列处理任务的引用
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
        self._last_request_time = 0
        self.min_request_interval = 0.1  # 最小请求间隔（秒）

    async def start(self):
        """启动队列处理器"""
        if self._queue_processor_task is None:
            self._queue_processor_task = asyncio.create_task(self._process_queue())

    async def _get_access_token(self) -> str:
        """获取access_token，增加提前刷新机制"""
        current_time = time.time()
        if (self.access_token and 
            current_time < self.token_expires_at - self.TOKEN_REFRESH_THRESHOLD):
            return self.access_token

        retries = 0
        while retries < self.max_retries:
            try:
                response = await self.client.post(
                    self.token_url,
                    json={"api_key": self.api_key},
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                token_data = response.json()
                self.access_token = token_data["access_token"]
                self.token_expires_at = time.time() + token_data["expires_in"]
                logger.debug("Successfully refreshed access token.")
                return self.access_token
            except Exception as e:
                retries += 1
                if retries < self.max_retries:
                    # 使用指数退避策略
                    delay = self.BASE_RETRY_DELAY * (2 ** (retries - 1))
                    await asyncio.sleep(delay)
                logger.error(f"Failed to refresh token (attempt {retries}): {e}")

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
        """发送HTTP请求，增加限流机制"""
        async with self._semaphore:  # 限制并发请求数
            # 确保请求间隔
            current_time = time.time()
            time_since_last_request = current_time - self._last_request_time
            if time_since_last_request < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - time_since_last_request)

            retries = 0
            while retries < self.max_retries:
                try:
                    headers = await self._get_headers()
                    response = await self.client.request(
                        method,
                        endpoint,
                        headers=headers,
                        **kwargs
                    )
                    response.raise_for_status()
                    self._last_request_time = time.time()
                    return response.json()
                except Exception as e:
                    retries += 1
                    if retries < self.max_retries:
                        # 使用指数退避策略
                        delay = self.BASE_RETRY_DELAY * (2 ** (retries - 1))
                        await asyncio.sleep(delay)
                    logger.error(f"Request failed (attempt {retries}): {e}")

            raise RuntimeError("HTTP request failed after maximum retries.")

    async def _process_queue(self):
        """处理请求队列中的任务"""
        while True:
            try:
                method, endpoint, future, kwargs = await self.request_queue.get()
                try:
                    result = await self._make_request(method, endpoint, **kwargs)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                finally:
                    self.request_queue.task_done()
            except asyncio.CancelledError:
                break

    async def enqueue_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """将请求加入队列，并返回 Future 对象"""
        if self._queue_processor_task is None:
            await self.start()
        
        future = asyncio.get_event_loop().create_future()
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
        """关闭 HTTP 客户端"""
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            await asyncio.gather(self._queue_processor_task, return_exceptions=True)
            self._queue_processor_task = None
        await self.client.aclose()
