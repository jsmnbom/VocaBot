import atexit
import logging
import sqlite3

from constants import DB_FILE

logger = logging.getLogger(__name__)

LANGS = ['en_GB']
VOCA_LANGS = ['Default', 'Japanese', 'Romaji', 'English']


class DBManager(object):
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.c = self.conn.cursor()

        self.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='options'")
        if not self.c.fetchone():
            self.new()

        atexit.register(self.close)

    def close(self):
        logging.debug("Committing and closing db.")
        self.conn.commit()
        self.conn.close()

    # noinspection PyUnusedLocal
    def commit(self, bot):
        logging.debug("Committing DB.")
        self.conn.commit()

    def new(self):
        # Options
        self.c.execute("CREATE TABLE options (chat_id INTEGER PRIMARY KEY)")
        self.c.execute("ALTER TABLE options ADD COLUMN 'lang' STRING")
        self.c.execute("ALTER TABLE options ADD COLUMN 'voca_lang' INTEGER")

        # Current operation with chat
        self.c.execute("CREATE TABLE state (chat_id STRING PRIMARY KEY)")
        self.c.execute("ALTER TABLE state ADD COLUMN 'state' STRING")
        self.c.execute("ALTER TABLE state ADD COLUMN 'data' STRING")
        self.conn.commit()

    def update_state(self, chat_id, current, data=''):
        self.c.execute("INSERT OR REPLACE INTO state VALUES (?, ?, ?)", (chat_id, current, data))

    def get_state(self, chat_id):
        self.c.execute("SELECT state,data FROM state WHERE chat_id=?", (chat_id,))
        try:
            fetch = self.c.fetchone()
        except TypeError:
            return None
        return fetch

    def remove_state(self, chat_id):
        self.c.execute("DELETE FROM state WHERE chat_id=?", (chat_id,))

    def set_lang(self, chat_id, lang):
        self.c.execute("INSERT OR REPLACE INTO options (chat_id,lang) VALUES (?,?)", (chat_id, lang))

    def get_lang(self, chat_id):
        self.c.execute("SELECT lang FROM options WHERE chat_id=?", (chat_id,))
        try:
            return self.c.fetchone()[0]
        except TypeError:
            return 'en_GB'

    def set_voca_lang(self, chat_id, lang):
        self.c.execute("INSERT OR REPLACE INTO options (chat_id,voca_lang) VALUES (?,?)",
                       (chat_id, VOCA_LANGS.index(lang)))

    def get_voca_lang(self, chat_id):
        self.c.execute("SELECT voca_lang FROM options WHERE chat_id=?", (chat_id,))
        try:
            return VOCA_LANGS[int(self.c.fetchone()[0])]
        except TypeError:
            return VOCA_LANGS[3]


db = DBManager()
