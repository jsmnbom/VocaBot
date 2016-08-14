import json
import logging

import requests
from cachecontrol import CacheControl
from cachecontrol.heuristics import ExpiresAfter

from constants import VOCADB_API_ENDPOINT, VOCADB_USER_AGENT, Context
from i18n import _

logger = logging.getLogger(__name__)


def escape_bad_html(text):
    # text = text.replace('&', '&#38;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


class VocaDB(object):
    def __init__(self):
        self.s = requests.Session()
        # We cache ALL responses for 60 min. so eg. inline lyrics request don't make two calls right after each other.
        # This MAY have unforeseen consequences, but hopefully we can deal with those.
        self.s = CacheControl(self.s, cache_etags=False, heuristic=ExpiresAfter(minutes=60))
        self.s.headers.update({'Accept': 'application/json', 'User-Agent': VOCADB_USER_AGENT})
        self.opts = {'nameMatchMode': 'Auto', 'getTotalCount': 'true'}
        self._resources = {}

    def set_name(self, name):
        self.s.headers.update({'user-agent': VOCADB_USER_AGENT.format(bot_name=name)})

    def base(self, api, params, process=True):
        if process:
            params.update(self.opts)
        r = self.s.get(VOCADB_API_ENDPOINT + api, params=params)
        if not r.status_code == requests.codes.ok:
            logger.warning('Problem with HTTP request.')
            # If it's a 404, it's probably because user did something stupid, so we ignore it
            if not r.status_code == 404:
                r.raise_for_status()
        logger.debug(r.text)
        try:
            # Not using request json recoder since we want to strip stuff that telegram doesn't like
            data = json.loads(escape_bad_html(r.text))
        except ValueError as e:
            logger.warning('Non-JSON returned from VocaDB API endpoint: %s', e)
            return None
        return data

    def entries(self, query, lang, max_results=3, sort='Name'):
        payload = {'query': query, 'lang': lang, 'fields': 'MainPicture, Names, PVs', 'sort': sort,
                   'maxResults': max_results}

        def page(i):
            payload.update({'start': (i - 1) * max_results})
            data = self.base('entries', payload)
            if data:
                found = data['items']
                return found, ((i - 1) * max_results, data['totalCount']), Context.search

        return page

    def songs(self, query, lang, max_results=3, sort='FavoritedTimes', artist_id=''):
        payload = {'query': query, 'lang': lang, 'fields': 'MainPicture, Names, Artists', 'sort': sort,
                   'maxResults': max_results, 'artistId': artist_id, 'preferAccurateMatches': 'true'}

        def page(i):
            payload.update({'start': (i - 1) * max_results})
            data = self.base('songs', payload)
            if data:
                found = data['items']
                return found, ((i - 1) * max_results, data['totalCount']), Context.search

        return page

    def artists(self, query, lang, max_results=3, sort='FollowerCount'):
        payload = {'query': query, 'lang': lang, 'fields': 'MainPicture, Names', 'sort': sort,
                   'maxResults': max_results, 'preferAccurateMatches': 'true'}

        def page(i):
            payload.update({'start': (i - 1) * max_results})
            data = self.base('artists', payload)
            if data:
                found = data['items']
                return found, ((i - 1) * max_results, data['totalCount']), Context.search

        return page

    def albums(self, query, lang, max_results=3, sort='NameThenReleaseDate'):
        payload = {'query': query, 'lang': lang, 'fields': 'MainPicture, Names', 'sort': sort,
                   'maxResults': max_results, 'preferAccurateMatches': 'true'}

        def page(i):
            payload.update({'start': (i - 1) * max_results})
            data = self.base('albums', payload)
            if data:
                found = data['items']
                return found, ((i - 1) * max_results, data['totalCount']), Context.search

        return page

    def song(self, song_id, fields, lang):
        payload = {'fields': fields, 'lang': lang}
        data = self.base('songs/{}'.format(song_id), payload)
        return data

    def artist(self, artist_id, fields, lang):
        payload = {'fields': fields, 'lang': lang}
        data = self.base('artists/{}'.format(artist_id), payload)
        return data

    def album(self, artist_id, fields, lang):
        payload = {'fields': fields, 'lang': lang}
        data = self.base('albums/{}'.format(artist_id), payload)
        return data

    def derived(self, song_id, lang, max_results=3):
        payload = {'fields': 'MainPicture', 'lang': lang}

        def page(i):
            offset = i * max_results
            data = self.base('songs/{}/derived'.format(song_id), payload)
            if data:
                m = offset + max_results
                if m > len(data):
                    m = offset + ((len(data) - offset) % max_results)
                d = data[offset:m]
                return d, ((i - 1) * max_results, len(data)), Context.derived
            else:
                return [], (0, 0), Context.derived

        return page

    # Hardcoded to 3 entries... because...
    def related(self, song_id, lang):
        payload = {'fields': 'MainPicture', 'lang': lang}

        def page(i):
            data = self.base('songs/{}/related'.format(song_id), payload)
            if data:
                r = []
                smallest = 100
                for match_type in ['artistMatches', 'likeMatches', 'tagMatches']:
                    if not data[match_type]:
                        break
                    r.append(data[match_type][i - 1])
                    smallest = len(data[match_type]) if len(data[match_type]) < smallest else smallest
                else:
                    return r, ((i - 1) * 3, smallest * 3), Context.related
            return [], (0, 0), Context.related

        return page

    def resources(self, culture_code, set_names=None):
        payload = {'setNames': set_names}
        data = self.base('resources/{}'.format(culture_code), payload, process=False)
        return data

    def trans(self, s, song=False, artist=False, album=False):
        if _.code not in self._resources:
            self._resources[_.code] = self.resources(_.code, ['songTypeNames', 'artistTypeNames', 'discTypeNames'])
        try:
            if song:
                return self._resources[_.code]['songTypeNames'][s]
            if artist:
                return self._resources[_.code]['artistTypeNames'][s]
            if album:
                return self._resources[_.code]['albumTypeNames'][s]
        except KeyError:
            return s


voca_db = VocaDB()
