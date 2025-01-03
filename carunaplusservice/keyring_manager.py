from getpass import getpass

import keyring


class KeyringManager:
    def __init__(self, service_name):
        self.service_name = service_name

    def get_value(self, key):
        return keyring.get_password(self.service_name, key)

    def set_value(self, key, value):
        keyring.set_password(self.service_name, key, value)

    def delete_value(self, key):
        keyring.delete_password(self.service_name, key)

    def prompt_for_value(self, key, prompt_message):
        value = self.get_value(key)
        if not value:
            value = (
                getpass(prompt_message)
                if "password" in key.lower()
                else input(prompt_message)
            )
            self.set_value(key, value)
        return value

    def prompt_for_credentials(self):
        username = self.prompt_for_value("username", "Username: ")
        password = self.prompt_for_value("password", "Password: ")
        return username, password

    def clear_credentials(self):
        self.delete_value("username")
        self.delete_value("password")
