import unittest

from forex.application.broker.use_cases import BrokerUseCases
from forex.config.paths import TOKEN_FILE
from forex.infrastructure.broker.fake.provider import FakeProvider


class BrokerUseCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.use_cases = BrokerUseCases(FakeProvider())

    def test_create_app_auth(self) -> None:
        service = self.use_cases.create_app_auth("demo", TOKEN_FILE)
        self.assertEqual(service.host_type, "demo")
        self.assertEqual(service.token_file, TOKEN_FILE)

    def test_create_oauth_login(self) -> None:
        service = self.use_cases.create_oauth_login(TOKEN_FILE, "http://localhost/callback")
        self.assertEqual(service.token_file, TOKEN_FILE)
        self.assertEqual(service.redirect_uri, "http://localhost/callback")

    def test_create_account_list(self) -> None:
        app_auth = self.use_cases.create_app_auth("demo", TOKEN_FILE)
        service = self.use_cases.create_account_list(app_auth, "access")
        service.set_access_token("new-access")
        self.assertTrue(hasattr(service, "in_progress"))
        self.assertTrue(callable(service.fetch))

    def test_fetch_accounts_updates_cached_access_token(self) -> None:
        app_auth = self.use_cases.create_app_auth("demo", TOKEN_FILE)
        result1 = self.use_cases.fetch_accounts(app_auth, "token-a")
        self.assertTrue(result1)

        cached_uc = self.use_cases._account_list_cache.use_case
        self.assertIsNotNone(cached_uc)
        self.assertEqual(cached_uc._adapter._service.access_token, "token-a")

        result2 = self.use_cases.fetch_accounts(app_auth, "token-b")
        self.assertTrue(result2)
        self.assertEqual(cached_uc._adapter._service.access_token, "token-b")

    def test_fetch_accounts_returns_false_when_in_progress(self) -> None:
        app_auth = self.use_cases.create_app_auth("demo", TOKEN_FILE)
        self.use_cases.fetch_accounts(app_auth, "token-a")
        cached_uc = self.use_cases._account_list_cache.use_case
        self.assertIsNotNone(cached_uc)
        cached_uc._adapter._service.in_progress = True

        result = self.use_cases.fetch_accounts(app_auth, "token-b")
        self.assertFalse(result)

    def test_fetch_symbols_invokes_callback(self) -> None:
        app_auth = self.use_cases.create_app_auth("demo", TOKEN_FILE)
        received = []

        result = self.use_cases.fetch_symbols(
            app_auth_service=app_auth,
            account_id=123,
            on_symbols_received=lambda symbols: received.append(symbols),
        )

        self.assertTrue(result)
        self.assertEqual(received, [[]])


if __name__ == "__main__":
    unittest.main()
