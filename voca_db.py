import json
import logging

import requests
from cachecontrol import CacheControl

from constants import VOCADB_API_ENDPOINT, voca_db_user_agent
from utils import escape_bad_html


# noinspection SpellCheckingInspection
class VocaDB(object):
    def __init__(self):
        self.s = requests.Session()
        self.s = CacheControl(self.s)
        self.s.headers.update({'user-agent': voca_db_user_agent})
        self.s.headers.update({'Accept': 'application/json'})
        self.opts = {'nameMatchMode': 'Auto', 'preferAccurateMatches': 'true',
                     'getTotalCount': 'true'}

    def base(self, api, params):
        params.update(self.opts)
        r = self.s.get(VOCADB_API_ENDPOINT + api, params=params)
        logging.debug(r.text)
        try:
            # Not using request json recoder since we want to strip stuff that telegram doesn't like
            data = json.loads(escape_bad_html(r.text))
        except ValueError as e:
            logging.warning('Non-JSON returned from VocaDB API endpoint: %s', e)
            return None
        return data

    def songs(self, query, lang, offset=0, max_results=10, sort='FavoritedTimes', artist_id=''):
        payload = {'query': query, 'lang': lang, 'start': offset or 0, 'fields': 'MainPicture',
                   'maxResults': max_results, 'sort': sort, 'artistId': artist_id}
        data = self.base('songs', payload)
        if data:
            found = data['items']
            return found, data['totalCount']

    def song(self, song_id, fields, lang):
        payload = {'fields': fields, 'lang': lang}
        data = self.base('songs/{}'.format(song_id), payload)
        return data

    def artists(self, query, lang, offset=0, max_results=10, sort='FollowerCount'):
        payload = {'query': query, 'lang': lang, 'start': offset or 0, 'fields': 'MainPicture',
                   'maxResults': max_results, 'sort': sort}
        data = self.base('artists', payload)
        if data:
            found = data['items']
            return found, data['totalCount']

    def artist(self, artist_id, fields, lang):
        payload = {'fields': fields, 'lang': lang}
        data = self.base('artists/{}'.format(artist_id), payload)
        return data

    def derived(self, song_id, lang, max_results=10, offset=1):
        payload = {'fields': 'MainPicture', 'lang': lang}
        data = self.base('songs/{}/derived'.format(song_id), payload)
        if data:
            m = offset + max_results - 1
            if m > len(data):
                m = offset + ((len(data) - offset) % max_results) - 1
            d = data[offset - 1:m]
            return d, len(data)
        else:
            return [], 0


voca_db = VocaDB()
