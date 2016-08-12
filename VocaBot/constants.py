from enum import Enum
from pathlib import Path

__version__ = "2.0.0"
VOCADB_API_ENDPOINT = "https://vocadb.net/api/"
VOCADB_BASE_URL = 'https://vocadb.net/'
OWNER_IDS = (95205500,)
DB_FILE = Path('../data.json')
VOCADB_USER_AGENT = 'Telegram-{bot_name}/{version}'.format(bot_name='{bot_name}', version=__version__)
LOCALE_FOLDER = 'i18n/locales'
LOCALE_NAME = 'VocaBot'

# noinspection SpellCheckingInspection
PV_SERVICES = ['SoundCloud', 'Youtube', 'NicoNicoDouga', 'Piapro', 'Vimeo', 'Bilibili']

# noinspection PyArgumentList
SettingState = Enum('SettingState', 'settings interface voca')
# noinspection PyArgumentList
BrowseState = Enum('BrowseState', 'input input_song input_artist input_album page')
# noinspection PyArgumentList
Context = Enum('ContentErrors', 'search derived related')