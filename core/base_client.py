# base_client.py
import httpx
import asyncio
import time
from browserforge.headers import HeaderGenerator
from urllib.parse import urljoin
from settings import PROXY_HOST, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD

from logger.logger import get_logger

logger = get_logger("BaseClient")

class BaseClient:
    """
    BaseClient is an asynchronous HTTP client wrapper that handles HTTP requests with retry logic,
    proxy support, and custom header generation.
    This class provides a foundation for making HTTP requests with built-in resilience features
    including exponential backoff retries, proxy configuration, and customizable timeouts.
    Attributes:
        base_url (str): The base URL for all requests. Trailing slashes are removed.
        retries (int): The number of retry attempts for failed requests. Defaults to 5.
        timeout (int): The timeout duration in seconds for each request. Defaults to 20.
        backoff (float): The backoff multiplier for exponential backoff between retries. Defaults to 2.5.
        proxies (str | None): The proxy URL to be used for requests, if configured. None if proxy is not enabled.
    Example:
        >>> client = BaseClient(
        ...     base_url="https://api.example.com",
        ...     use_proxy=True,
        ...     retries=3,
        ...     timeout=30,
        ...     backoff=2.0
        ... )
        >>> response = await client._request("GET", "/users")
    """
    def __init__(self, base_url: str, use_proxy: bool = False, retries: int | bool = 5, timeout: int = 60, backoff: float = 2.5):
        self.base_url = base_url.rstrip("/")
        self.retries = 5 if retries is True else (1 if retries is False else retries)
        self.timeout = timeout
        self.backoff = backoff
        self.proxies = None

        if use_proxy:
            if PROXY_HOST and PROXY_PORT:
                proxy_url_base = f"{PROXY_HOST}:{PROXY_PORT}"
                proxy_url = f"http://{proxy_url_base}"
                
                if PROXY_USERNAME and PROXY_PASSWORD:
                    proxy_auth = f"{PROXY_USERNAME}:{PROXY_PASSWORD}@"
                    proxy_url = f"http://{proxy_auth}{proxy_url_base}"

                self.proxies = proxy_url

                logger.info("Using proxy configuration from .env file")
            else:
                logger.warning("`use_proxy` is True, but PROXY_HOST and PROXY_PORT not found in .env file.")

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """
        Sends an asynchronous HTTP request to the specified endpoint.
        This method constructs the full URL by joining the base URL with the provided endpoint,
        generates custom headers using the HeaderGenerator, and merges them with any headers
        provided in the request parameters. It supports retries in case of request errors.
        Args:
            method (str): The HTTP method to use for the request (e.g., 'GET', 'POST').
            endpoint (str): The endpoint to which the request is sent.
            **kwargs: Additional keyword arguments that can include:
                - headers (dict): Custom headers to include in the request.
                - params (dict): URL parameters to include in the request.
                - json (dict): JSON data to send in the request body.
        Returns:
            dict: A dictionary containing the response status, headers, cookies, and body.
        Raises:
            httpx.RequestError: If the request fails after the specified number of retries.
        """
        
        url = urljoin(self.base_url, endpoint)

        hg = HeaderGenerator(device='desktop', locale='en-US', http_version=2)
        try:
            custom_headers = hg.generate() if hasattr(hg, "generate") else getattr(hg, "headers", {})
        except Exception as e:
            logger.warning(f"Failed to generate headers from HeaderGenerator: {e}")
            custom_headers = {}

        param_headers = kwargs.get('headers', None)

        if param_headers:
            if isinstance(param_headers, dict):
                merged_headers = {**custom_headers, **param_headers}
            else:
                logger.warning("Request headers passed are not a dict; keeping them unchanged.")
                merged_headers = param_headers
        else:
            merged_headers = custom_headers

        kwargs['headers'] = merged_headers

        for attempt in range(1, self.retries + 1):
            try:
                async with httpx.AsyncClient(http2=True,proxy=self.proxies, timeout=self.timeout) as client:
                    response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return {
                    "status": response.status_code,
                    "headers": dict(response.headers),
                    "cookies": dict(response.cookies),
                    "body": response.text
                }
            except httpx.RequestError as e:
                sleep_time = self.backoff ** attempt
                await asyncio.sleep(sleep_time)
        
        return {}
