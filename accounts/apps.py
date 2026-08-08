from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        # signals.py is deleted — BankAccount creation now happens
        # explicitly inside register_view for clarity and reliability.
        pass
