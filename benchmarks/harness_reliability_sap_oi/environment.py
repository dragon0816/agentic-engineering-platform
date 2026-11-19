"""Process-only isolation from the owner's daily Telegram settings."""

import os


def disable_test_telegram() -> None:
    """Owner: 141 tests must not inherit daily Telegram bot credentials/settings.

    Only this benchmark process and its children are affected; never modify the
    Windows user environment or another host's configuration.
    """
    for name in tuple(os.environ):
        if name.upper().startswith(("TELEGRAM_", "AEP_TELEGRAM_")):
            os.environ.pop(name, None)
