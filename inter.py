import gettext
import os.path
from pathlib import Path

from flufl.i18n import registry


class Strategy(object):
    """Strategy for flufl's translation stuff. Adapted from _BaseStrategy in _strategy of flufl module."""

    def __init__(self, name, folder=None):
        self.name = name
        if folder is None:
            self.folder = os.path.dirname(__file__)
        else:
            self.folder = str(folder)

    def __call__(self, language_code=None):
        languages = (None if language_code is None else [language_code])
        try:
            return gettext.translation(
                self.name, self.folder, languages)
        except IOError:
            return gettext.NullTranslations()


locale_folder = 'i18n/locales'
strategy = Strategy('VocaBot', folder=Path(locale_folder))

application = registry.register(strategy)

underscore = application._
