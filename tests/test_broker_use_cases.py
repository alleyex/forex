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


if __name__ == "__main__":
    unittest.main()
