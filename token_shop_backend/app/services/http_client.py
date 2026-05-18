# app/services/http_client.py
import asyncio, logging
from typing import Any
import aiohttp

log = logging.getLogger("http")

class HttpClient:
    def __init__(
        self,
        timeout_sec: int = 12,
        retries: int = 3,
        limit_per_host: int = 20,
        default_headers: dict[str, str] | None = None,
    ):
        self.timeout = aiohttp.ClientTimeout(
            total=timeout_sec,
            connect=min(10, max(2, timeout_sec // 3)),
            sock_read=None,
        )
        self.retries = max(1, retries)
        self.default_headers = dict(default_headers or {})

        # Tối ưu connection pool cho high concurrency (4-50 người cùng lúc)
        # Tăng limit để xử lý nhiều request song song
        self.connector = aiohttp.TCPConnector(
            limit=150,  # Tổng số connection tối đa (tăng từ 100 lên 150)
            limit_per_host=limit_per_host * 2,  # Tăng per host limit để xử lý nhiều request đồng thời hơn
            keepalive_timeout=180,  # Giữ connection lâu hơn (3 phút) để reuse connection
            ttl_dns_cache=600,  # Cache DNS 10 phút để giảm DNS lookup
            enable_cleanup_closed=True,  # Tự động cleanup connections đã đóng
            force_close=False,  # Reuse connections để tăng hiệu suất
            use_dns_cache=True,  # Bật DNS cache
        )
        self.session = aiohttp.ClientSession(
            timeout=self.timeout, 
            connector=self.connector,
            # Không set json_serialize để dùng default (json.dumps)
            trust_env=True,  # Trust environment variables cho proxy
        )

    async def close(self):
        await self.session.close()

    async def request(self, method: str, url: str, json: dict | None = None, headers: dict | None = None, params: dict | None = None) -> Any:
        last_err = None
        for attempt in range(1, self.retries + 1):
            try:
                request_headers = dict(self.default_headers)
                if headers:
                    request_headers.update(headers)

                async with self.session.request(method, url, json=json, headers=request_headers or None, params=params) as resp:
                    ct = resp.headers.get("Content-Type", "") or ""
                    
                    if resp.status >= 500:
                        # Đọc error message trước khi raise
                        try:
                            error_text = await resp.text()
                        except Exception:
                            error_text = f"Server error {resp.status}"
                        raise RuntimeError(f"server_error:{resp.status}:{error_text}")

                    # Parse response body - đảm bảo không None
                    data = None
                    try:
                        if "application/json" in ct:
                            json_data = await resp.json()
                            data = json_data if json_data is not None else {}
                        else:
                            text_data = await resp.text()
                            data = text_data if text_data is not None else ""
                    except Exception as parse_err:
                        # Nếu không parse được, đọc text
                        try:
                            text_data = await resp.text()
                            data = text_data if text_data is not None else f"Failed to parse response: {parse_err}"
                        except Exception as text_err:
                            data = f"Failed to parse response: {parse_err}, text_err: {text_err}"
                    
                    # Đảm bảo data không None
                    if data is None:
                        data = ""

                    if resp.status >= 400:
                        # FastAPI trả về error dạng JSON: {"detail": "OUT_OF_STOCK"}
                        error_detail = data
                        if isinstance(data, dict):
                            error_detail = data.get("detail", str(data))
                        elif isinstance(data, str):
                            # Thử parse JSON string nếu có
                            try:
                                import json
                                parsed = json.loads(data)
                                if isinstance(parsed, dict):
                                    error_detail = parsed.get("detail", data)
                            except:
                                pass
                        
                        # Không retry cho 4xx errors (client errors)
                        if resp.status < 500:
                            raise RuntimeError(f"http_error:{resp.status}:{error_detail}")
                        raise RuntimeError(f"http_error:{resp.status}:{error_detail}")
                    return data
            except aiohttp.ClientError as e:
                last_err = RuntimeError(f"connection_error:{str(e)}")
                if attempt == self.retries:
                    log.warning("HTTP %s %s attempt=%s/%s err=%s", method, url, attempt, self.retries, last_err)
                if attempt < self.retries:
                    delay = min(0.2 * (2 ** (attempt - 1)), 1.0)
                    await asyncio.sleep(delay)
            except RuntimeError as e:
                last_err = e
                msg = str(e)
                # Do not retry client-side errors (4xx) except when explicitly handled elsewhere.
                if msg.startswith("http_error:4"):
                    raise
                if attempt == self.retries:
                    log.warning("HTTP %s %s attempt=%s/%s err=%s", method, url, attempt, self.retries, e)
                if attempt < self.retries:
                    delay = min(0.2 * (2 ** (attempt - 1)), 1.0)
                    await asyncio.sleep(delay)
            except Exception as e:
                last_err = e
                # Chỉ log lần cuối để giảm overhead
                if attempt == self.retries:
                    log.warning("HTTP %s %s attempt=%s/%s err=%s", method, url, attempt, self.retries, e)
                # Exponential backoff với jitter để tránh thundering herd
                if attempt < self.retries:
                    delay = min(0.2 * (2 ** (attempt - 1)), 1.0)
                    await asyncio.sleep(delay)
        
        if last_err:
            raise last_err
        raise RuntimeError("HTTP request failed after all retries")
