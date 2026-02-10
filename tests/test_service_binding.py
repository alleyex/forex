from __future__ import annotations

import unittest

from forex.ui.shared.controllers.service_binding import clear_log_history_safe, set_callbacks_safe


class ServiceWithClear:
    def __init__(self) -> None:
        self.cleared = False

    def clear_log_history(self) -> None:
        self.cleared = True


class ServiceWithStrictCallbacks:
    def __init__(self) -> None:
        self.called = False
        self.received = {}

    def set_callbacks(self, on_log=None, on_status_changed=None) -> None:
        self.called = True
        self.received = {
            "on_log": on_log,
            "on_status_changed": on_status_changed,
        }


class ServiceWithKwargCallbacks:
    def __init__(self) -> None:
        self.received = {}

    def set_callbacks(self, **callbacks) -> None:
        self.received = callbacks


class ServiceBindingTest(unittest.TestCase):
    def test_clear_log_history_safe_calls_service_method(self) -> None:
        service = ServiceWithClear()
        clear_log_history_safe(service)
        self.assertTrue(service.cleared)

    def test_clear_log_history_safe_ignores_missing_method(self) -> None:
        clear_log_history_safe(object())

    def test_set_callbacks_safe_filters_unsupported_callback_names(self) -> None:
        service = ServiceWithStrictCallbacks()
        on_log = lambda msg: msg  # noqa: E731
        on_status = lambda status: status  # noqa: E731
        on_unknown = lambda value: value  # noqa: E731

        set_callbacks_safe(
            service,
            on_log=on_log,
            on_status_changed=on_status,
            on_unknown=on_unknown,
        )

        self.assertTrue(service.called)
        self.assertIs(service.received["on_log"], on_log)
        self.assertIs(service.received["on_status_changed"], on_status)

    def test_set_callbacks_safe_passes_all_callbacks_for_kwargs_signature(self) -> None:
        service = ServiceWithKwargCallbacks()
        on_log = lambda msg: msg  # noqa: E731
        on_error = lambda err: err  # noqa: E731

        set_callbacks_safe(service, on_log=on_log, on_error=on_error)

        self.assertIs(service.received["on_log"], on_log)
        self.assertIs(service.received["on_error"], on_error)


if __name__ == "__main__":
    unittest.main()
