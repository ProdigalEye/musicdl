'''
Function:
    Implementation of MituMusicClient: https://www.qqmp3.vip/
Author:
    Zhenchao Jin
WeChat Official Account (微信公众号):
    Charles的皮卡丘
'''
import os
import copy
from .base import BaseMusicClient
from urllib.parse import urlencode
from rich.progress import Progress
from ..utils import legalizestring, resp2json, usesearchheaderscookies, AudioLinkTester, WhisperLRC


'''MituMusicClient'''
class MituMusicClient(BaseMusicClient):
    source = 'MituMusicClient'
    def __init__(self, **kwargs):
        super(MituMusicClient, self).__init__(**kwargs)
        self.default_search_headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "origin": "https://www.qqmp3.vip",
            "priority": "u=1, i",
            "referer": "https://www.qqmp3.vip/",
            "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        }
        self.default_download_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        }
        self.default_headers = self.default_search_headers
        self._initsession()
    '''_constructsearchurls'''
    def _constructsearchurls(self, keyword: str, rule: dict = None, request_overrides: dict = None):
        # init
        rule, request_overrides = rule or {}, request_overrides or {}
        # search rules
        default_rule = {'keyword': keyword, 'type': 'search'}
        default_rule.update(rule)
        # construct search urls based on search rules
        base_url = 'https://api.qqmp3.vip/api/songs.php?'
        page_rule = copy.deepcopy(default_rule)
        search_urls = [base_url + urlencode(page_rule)]
        self.search_size_per_page = self.search_size_per_source
        # return
        return search_urls
    '''_search'''
    @usesearchheaderscookies
    def _search(self, keyword: str = '', search_url: str = '', request_overrides: dict = None, song_infos: list = [], progress: Progress = None, progress_id: int = 0):
        # init
        request_overrides = request_overrides or {}
        # successful
        try:
            # --search results
            resp = self.get(search_url, **request_overrides)
            resp.raise_for_status()
            search_results = resp2json(resp)['data']
            for search_result in search_results:
                # --download results
                if 'rid' not in search_result:
                    continue
                download_url = search_result.get('src')
                if not download_url: continue
                download_url_status = AudioLinkTester(headers=self.default_download_headers, cookies=self.default_download_cookies).test(download_url, request_overrides)
                if not download_url_status['ok']: continue
                download_result = AudioLinkTester(headers=self.default_download_headers, cookies=self.default_download_cookies).probe(download_url, request_overrides)
                if download_result['ext'] == 'NULL': download_result['ext'] = 'mp3'
                # --lyric results
                try:
                    if os.environ.get('ENABLE_WHISPERLRC', 'False').lower() == 'true':
                        lyric_result = WhisperLRC(model_size_or_path='small').fromurl(
                            download_url, headers=self.default_download_headers, cookies=self.default_download_cookies, request_overrides=request_overrides
                        )
                        lyric = lyric_result['lyric']
                    else:
                        lyric_result, lyric = dict(), 'NULL'
                except:
                    lyric_result, lyric = dict(), 'NULL'
                # --construct song_info
                song_info = dict(
                    source=self.source, raw_data=dict(search_result=search_result, download_result=download_result, lyric_result=lyric_result), 
                    download_url_status=download_url_status, download_url=download_url, ext=download_result['ext'], file_size=download_result['file_size'], 
                    lyric=lyric, duration='-:-:-', song_name=legalizestring(search_result.get('name', 'NULL'), replace_null_string='NULL'), 
                    singers=legalizestring(search_result.get('artist', 'NULL'), replace_null_string='NULL'), album='NULL', identifier=search_result['rid'],
                )
                # --append to song_infos
                song_infos.append(song_info)
                # --judgement for search_size
                if self.strict_limit_search_size_per_page and len(song_infos) >= self.search_size_per_page: break
            # --update progress
            progress.advance(progress_id, 1)
            progress.update(progress_id, description=f"{self.source}.search >>> {search_url} (Success)")
        # failure
        except Exception as err:
            progress.update(progress_id, description=f"{self.source}.search >>> {search_url} (Error: {err})")
        # return
        return song_infos