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

import os
import re

from gevent.lock import Semaphore

from ... import hoster
from bs4 import BeautifulSoup

@hoster.host
class this:
    model = hoster.HttpHoster
    name = 'streamcloud.eu'
    max_chunks = 2
    global_max_check_tasks = 1
    patterns = [
        hoster.Matcher('https?', '*.streamcloud.eu', '!/<id>'),
    ]
    url_template =  'http://streamcloud.eu/{id}'

    has_captcha = False
    max_download_speed = 100
    waiting_time = 0

def set_name(file, data):
    name, ext = os.path.splitext(data['fname'])
    name += '.mp4'
    file.set_infos(name=name)

lock = Semaphore()

def get_url(file):
    resp = file.account.get(file.url)
    if not u'jwplayer("mediaplayer").setup({' in resp.text:
        action, data = get_start_form(resp, file)
        set_name(file, data)
        file.wait(11)
        resp = file.account.post(file.url, data=data)
    m = re.search(r'file:\s*"(http://(stor|cdn)\d+\.streamcloud\.eu(:\d+)?/[\d\w]+/video\.mp4)"', resp.text)
    if not m:
        print resp.text
    return m.group(1)

def get_start_form(resp, file):
    if resp.text.strip() == u'Not Found' or u"<h1>File Not Found</h1>" in resp.text:
        file.set_offline()

    s = BeautifulSoup(resp.text)
    form = s.select('form.proform')
    if not form:
        print resp.text
    return hoster.serialize_html_form(form[0])

def on_check(file):
    url = get_url(file)
    resp = file.account.get(url, stream=True)
    try:
        file.set_infos(size=resp.headers['Content-Length'])
    finally:
        resp.close()

def on_download(chunk):
    return get_url(chunk.file)
