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

import re

from ... import hoster

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = '4shared.com'
    patterns = [
        hoster.Matcher('https?', ['*.4shared.com', '*.4shared-china.com'], r'/(account/)?(?P<kind>download|get|file|document|photo|video|audio|office)/(?P<id>.+?)/((?P<name>.*)\.html?)?'),
    ]
    url_template = 'http://www.4shared.com/{kind}/{id}/'

def on_check(file):
    resp = file.account.get(file.url)

    if re.search(r'The file link that you requested is not valid\.|This file was deleted\.', resp.text):
        file.set_offline()

    m = re.search(r'<meta name="title" content="(.+?)"', resp.text)
    if not m:
        file.set_offline('filename not found')
    name = m.group(1)

    m = re.search(r'class="fileOwner[^"]+">[^<]*</a>\s*([0-9,.]+ [kKMG])i?B', resp.text, re.MULTILINE)
    if not m:
        file.set_offline('filesize not found')
    size = m.group(1)

    file.set_infos(name=name, approx_size=size)

def on_download_premium(chunk):
    raise NotImplementedError()

def on_download_free(chunk):
    resp = chunk.account.get(chunk.file.url)
    m = re.search(r'id="btnLink" href="(.*?)"', resp.text)
    if m:
        url = m.group(1)
    else:
        url = re.sub(r'/(download|get|file|document|photo|video|audio)/', r'/get/', chunk.file.url)

    resp = chunk.account.get(url)
    m = re.search(r'name="d3link" value="(.*?)"', resp.text)
    if not m:
        m = re.search(r'<img src="(.*?)" alt="[^"]+" id="imageM" title="Click to enlarge"', resp.text)
        if not m:
            chunk.no_download_link()
    url = m.group(1)

    # check download limit (ignored currently)
    """m = re.search(r'name="d3fid" value="(.*?)"', resp.text)
    if m:
        r = chunk.account.get('http://www.4shared.com/web/d2/getFreeDownloadLimitInfo', params={'fileId': m.group(1)})
        print r.text"""

    chunk.wait(20)
    return url

def on_initialize_account(self):
    self.sid = None

    self.get("http://www.4shared.com/main/translate/setLang.jsp", params={"silent": "true", "lang": "en"})

    if self.username is None:
        return False

    data = {"login": self.username, "password": self.password, "remember": "false", "doNotRedirect": "true"}
    resp = self.post('http://www.4shared.com/login', data=data)
    json = resp.json()

    if not "ok" in json or json['ok'] is not True:
        if "rejectReason" in json and json['rejectReason'] is not True:
            self.fatal(json['rejectReason'])
        self.login_failed()

    self.expires = None
    self.traffic = None
    self.premium = False
