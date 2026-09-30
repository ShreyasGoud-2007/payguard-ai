import unittest

import httpx

from app.services.nova_client import NovaApiError, NovaClient


class NovaClientTests(unittest.TestCase):
    def test_list_resource_follows_all_offset_pages(self):
        requested_offsets = []

        def handler(request):
            offset = int(request.url.params["offset"])
            requested_offsets.append(offset)
            page = [
                {"id": f"record-{index}"}
                for index in range(offset, min(offset + 2, 5))
            ]
            return httpx.Response(
                200,
                json={
                    "data": page,
                    "pagination": {
                        "offset": offset,
                        "limit": 2,
                        "total": 5,
                        "has_more": offset + len(page) < 5,
                    },
                },
            )

        client = NovaClient(
            "test-secret",
            page_size=2,
            transport=httpx.MockTransport(handler),
        )
        try:
            records = client.list_vendors()
        finally:
            client.close()

        self.assertEqual(requested_offsets, [0, 2, 4])
        self.assertEqual([record["id"] for record in records], [
            "record-0", "record-1", "record-2", "record-3", "record-4"
        ])

    def test_429_retry_after_and_502_backoff_are_honored(self):
        responses = [
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(502),
            httpx.Response(200, json={"data": [{"id": "vendor-1"}], "pagination": {"has_more": False}}),
        ]
        delays = []

        def handler(_request):
            return responses.pop(0)

        client = NovaClient(
            "test-secret",
            max_retries=2,
            retry_backoff_seconds=0.5,
            sleep=delays.append,
            transport=httpx.MockTransport(handler),
        )
        try:
            records = client.list_vendors()
        finally:
            client.close()

        self.assertEqual(len(records), 1)
        self.assertEqual(delays, [2.0, 1.0])

    def test_permanent_401_is_not_retried_and_secret_is_not_in_error(self):
        attempts = []

        def handler(_request):
            attempts.append(1)
            return httpx.Response(401, text="secret must not escape")

        client = NovaClient(
            "never-return-this-secret",
            max_retries=4,
            transport=httpx.MockTransport(handler),
        )
        try:
            with self.assertRaises(NovaApiError) as context:
                client.get_me()
        finally:
            client.close()

        self.assertEqual(len(attempts), 1)
        self.assertEqual(context.exception.status_code, 401)
        self.assertNotIn("never-return-this-secret", str(context.exception))
        self.assertNotIn("secret must not escape", str(context.exception))

    def test_auth_header_is_server_side_bearer(self):
        observed = {}

        def handler(request):
            observed["authorization"] = request.headers.get("Authorization")
            return httpx.Response(200, json={"data": {"id": "account"}})

        client = NovaClient(
            "unit-test-key",
            transport=httpx.MockTransport(handler),
        )
        try:
            result = client.get_me()
        finally:
            client.close()

        self.assertEqual(observed["authorization"], "Bearer unit-test-key")
        self.assertEqual(result, {"id": "account"})


if __name__ == "__main__":
    unittest.main()
