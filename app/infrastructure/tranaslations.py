import json
import os
from contextvars import ContextVar

current_locale = ContextVar("current_locale", default="en")


class TranslationManager:
    def __init__(self):
        # Вычисляем путь к папке translations относительно этого файла
        # app/infrastructure/tranaslations.py -> вверх на 3 уровня -> корень appp
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.translations_dir = os.path.join(base_dir, 'translations')

        print(f"DEBUG: Init TranslationManager. Looking for translations in: {self.translations_dir}")

        self.translations = {
            'en': self._load_translations('en.json'),
            'ru': self._load_translations('ru.json')
        }

        # Проверка загрузки
        en_count = len(self.translations['en'])
        ru_count = len(self.translations['ru'])
        print(f"DEBUG: Loaded translations - EN: {en_count} keys, RU: {ru_count} keys")

    def _load_translations(self, filename):
        path = os.path.join(self.translations_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"ERROR: Failed to load translation {filename}: {e}")
                return {}
        else:
            print(f"ERROR: Translation file not found: {path}")
            return {}

    def gettext(self, key, replacements=None, locale=None, **kwargs):
        """
        Метод принимает **kwargs для поддержки именованных аргументов (title=...).
        """
        # 1. Если локаль не передана явно, берем из контекста (установленного Middleware)
        if not locale:
            locale = current_locale.get()
            # print(f"DEBUG: gettext context locale: {locale}") # Раскомментируйте для детальной отладки

        dictionary = self.translations.get(locale, self.translations.get('en', {}))
        text = dictionary.get(key, key)

        # 2. Объединяем replacements и kwargs
        if replacements is None:
            replacements = kwargs
        else:
            replacements.update(kwargs)

        # 3. Форматируем строку
        if replacements:
            try:
                return text.format(**replacements)
            except KeyError:
                return text
        return text

    def get_supported_locales(self):
        return list(self.translations.keys())