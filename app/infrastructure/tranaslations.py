import json
import os
from contextvars import ContextVar

current_locale = ContextVar("current_locale", default="en")

class TranslationManager:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.translations_dir = os.path.join(base_dir, 'translations')

        self.translations = {
            'en': self._load_translations('en.json'),
            'ru': self._load_translations('ru.json')
        }

    def _load_translations(self, filename):
        path = os.path.join(self.translations_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading translation {filename}: {e}")
                return {}
        else:
            print(f"Translation file not found: {path}")
            return {}

    def gettext(self, key, replacements=None, locale=None):
        if not locale:
            locale = current_locale.get()

        dictionary = self.translations.get(locale, self.translations.get('en', {}))

        text = dictionary.get(key, key)

        if replacements:
            try:
                return text.format(**replacements)
            except KeyError:
                return text
        return text

    def get_supported_locales(self):
        return list(self.translations.keys())