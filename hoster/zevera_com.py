# -*- coding: utf-8 -*-
"""Copyright (C) 2013 COLDWELL AG

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
"""

import time
import gevent

from ... import hoster, event
from ...config import globalconfig

config = globalconfig.new('hoster').new('zevera.com')
config.default('request_timeout', 30, int)

@hoster.host
class this:
    model = hoster.MultiHttpPremiumHoster
    name = 'zevera.com'
    model = hoster.MultiHttpHoster
    max_chunks = 1
    can_resume = False

request_cache = dict()

def delete_request_cache(file_id):
    if file_id in request_cache:
        del request_cache[file_id]

def on_check(file):
    if call_api(file.account, str, cmd='checklink', olink=file.url, login=file.account.username, password=file.account.password) != 'Alive':
        file.set_offline('file is offline')

    resp = get_download_response(file, file)
    request_cache[file.id] = resp
    gevent.spawn_later(config['request_timeout'], delete_request_cache, file.id)

    name = hoster.contentdisposition.parse(resp.headers['Content-Disposition'])

    file.set_infos(name=name, size=int(resp.headers['Content-Length']))

def get_download_response(file, exc):
    url = "http://api.zevera.com/getFiles.aspx"
    params = {'ourl': file.url}

    if file.id in request_cache:
        resp = request_cache[file.id]
        del request_cache[file.id]
    else:
        with gevent.Timeout(config['request_timeout']):
            try:
                resp = file.account.get(url, params=params, stream=True)
            except gevent.Timeout:
                if file.retry_num < 3:
                    exc.retry('request timed out', 1)
                else:
                    exc.fatal('request timed out')

    if not 'Content-Length' in resp.headers:
        exc.fatal('missing Content-Length header')
    if not 'Content-Disposition' in resp.headers:
        if "<strong>We regret to inform you that for the time being our system has reached its traffic limits" in resp.text:
            exc.retry('file reached download limit', 1800)
        else:
            print resp.text
        exc.fatal('missing Content-Disposition header')

    return resp

def on_download(chunk):
    return get_download_response(chunk.file, chunk)


def call_api(account, type, **params):
    if 'password' in params:
        params['pass'] = params['password']
        del params['password']

    headers = {"Agent": "JDOWNLOADER", "Accept-Language": "en-gb, en;q=0.9, de;q=0.8"}
    resp = account.get("http://www.zevera.com/jDownloader.ashx", params=params, headers=headers)
    text = resp.text.replace(',', '\n')
    if type == dict:
        return dict((y.strip().lower(), z.strip()) for y, z in [x.split(':', 1) for x in text.splitlines() if ':' in x])
    elif type == list:
        return resp.text.strip().split(',')
    else:
        return resp.text

def on_initialize_account(self):
    if not self.username:
        self.premium = False
        return

    result = call_api(self, dict, cmd='accountinfo', login=self.username, password=self.password)
    if not result:
        self.login_failed()

    self.get("http://api.zevera.com/", allow_redirects=False)

    params = {"login": self.username, "pass": self.password}
    self.get("http://api.zevera.com/OfferLogin.aspx", params=params, allow_redirects=False)

    if not ".ASPNETAUTH" in self.browser.cookies:
        self.login_failed()

    self.expires = result['endsubscriptiondate']
    self.premium = self.expires > time.time() and True or False
    self.traffic = int(result['availabletodaytraffic'])*1024*1024

    hosts = call_api(self, list, cmd='gethosters')
    self.set_compatible_hosts(hosts)

    event.fire('account.{}:initialized'.format(self.name)) # for debug
