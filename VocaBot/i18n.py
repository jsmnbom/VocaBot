import gettext
import os.path
from pathlib import Path

from flufl.i18n import registry

from VocaBot.constants import LOCALE_NAME, LOCALE_FOLDER


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


strategy = Strategy(LOCALE_NAME, folder=Path(LOCALE_FOLDER))
application = registry.register(strategy)
# noinspection PyProtectedMember
_ = application._
