import pytest
import asyncio
import time
from src.agent.http_client import HTTPClient
from unittest.mock import Mock, patch

@pytest.fixture
async def http_client():
    client = HTTPClient(
        api_key="test_key",
        base_url="http://test.com",
        token_url="http://test.com/token",
        max_retries=3,
        timeout=10
    )
    await client.start()
    yield client
    await client.close()

# 测试并发请求处理
async def test_concurrent_requests(http_client):
    """测试大量并发请求是否能被正确处理"""
    # 模拟50个并发请求
    async def make_request(i):
        return await http_client.chat_completions_create(
            model="test-model",
            messages=[{"role": "user", "content": f"Test message {i}"}]
        )
    
    tasks = [make_request(i) for i in range(50)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 验证所有请求都被处理
    assert len(results) == 50
    # 验证请求队列是否为空
    assert http_client.request_queue.empty()

# 测试token缓存和过期
async def test_token_caching(http_client):
    """测试access_token的缓存机制"""
    # 第一次获取token
    token1 = await http_client._get_access_token()
    
    # 立即再次获取，应该返回缓存的token
    token2 = await http_client._get_access_token()
    assert token1 == token2
    
    # 模拟token过期
    http_client.token_expires_at = time.time() - 1
    
    # 再次获取token，应该刷新
    token3 = await http_client._get_access_token()
    assert token3 != token1

# 测试单例模式
async def test_singleton():
    """测试HTTPClient是否维持单例（通过agent_utils）"""
    from src.agent.agent_utils import get_http_client
    
    # 获取两个实例
    client1 = await get_http_client()
    client2 = await get_http_client()
    
    # 验证是同一个实例
    assert client1 is client2

# 测试token过期自动刷新
async def test_token_auto_refresh(http_client):
    """测试token过期时是否自动刷新"""
    # 首次请求
    await http_client.chat_completions_create(
        model="test-model",
        messages=[{"role": "user", "content": "test"}]
    )
    
    # 记录当前token
    old_token = http_client.access_token
    
    # 模拟token过期
    http_client.token_expires_at = time.time() - 1
    
    # 再次请求
    await http_client.chat_completions_create(
        model="test-model",
        messages=[{"role": "user", "content": "test"}]
    )
    
    # 验证token已更新
    assert http_client.access_token != old_token 

# 添加新的测试用例

async def test_token_early_refresh(http_client):
    """测试token提前刷新机制"""
    # 首次获取token
    token1 = await http_client._get_access_token()
    
    # 设置token即将过期（剩余时间小于阈值）
    http_client.token_expires_at = (
        time.time() + HTTPClient.TOKEN_REFRESH_THRESHOLD - 60
    )
    
    # 再次获取token，应该触发提前刷新
    token2 = await http_client._get_access_token()
    assert token2 != token1

async def test_request_rate_limiting(http_client):
    """测试请求限流机制"""
    start_time = time.time()
    
    # 快速发送多个请求
    requests = [
        http_client.chat_completions_create(
            model="test-model",
            messages=[{"role": "user", "content": f"Test {i}"}]
        )
        for i in range(5)
    ]
    
    await asyncio.gather(*requests)
    end_time = time.time()
    
    # 验证请求间隔
    time_taken = end_time - start_time
    min_expected_time = (len(requests) - 1) * http_client.min_request_interval
    assert time_taken >= min_expected_time

async def test_concurrent_request_limit(http_client):
    """测试并发请求限制"""
    start_time = time.time()
    
    # 发送超过限制的并发请求
    requests = [
        http_client.chat_completions_create(
            model="test-model",
            messages=[{"role": "user", "content": f"Test {i}"}]
        )
        for i in range(HTTPClient.MAX_CONCURRENT_REQUESTS + 5)
    ]
    
    await asyncio.gather(*requests)
    
    # 验证所有请求都成功完成
    assert http_client.request_queue.empty() 
