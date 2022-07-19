import logging

import aiohttp

logger = logging.getLogger(__name__)


class APIError(Exception):

    def __init__(self, message, original=None):
        self.message = message
        if original:
            self.message += f" - {original.message} ({original.status})"
        super().__init__(self.message)


class APIClientError(APIError):

    def __init__(self, original):
        message = "Invalid Request"
        super().__init__(message, original)


class APIServerError(APIError):

    def __init__(self, original):
        message = "Server Error"
        super().__init__(message, original)


class APIClient:

    def __init__(self, *args, **kwargs):
        self._session = aiohttp.ClientSession(*args, **kwargs, raise_for_status=True)

    async def request(self, method, url, return_json=False, **kwargs):

        try:
            logger.debug(f"Outgoing request: {method} {url}")
            resp = await self._session.request(method, url, **kwargs)
            return await resp.json() if return_json else await resp.text()
        except aiohttp.ClientResponseError as error:
            if 400 <= error.status < 500:
                output_error = APIClientError(error)
            else:
                output_error = APIServerError(error)
            raise output_error from error
        except aiohttp.ClientError as error:
            output_error = APIError(str(error))
            raise output_error from error

    async def get(self, url, return_json=False, **kwargs):
        return await self.request("GET", url, return_json=return_json, **kwargs)

    async def post(self, url, return_json=False, **kwargs):
        return await self.request("POST", url, return_json=return_json, **kwargs)
