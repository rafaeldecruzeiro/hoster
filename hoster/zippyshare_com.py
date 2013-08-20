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

from ... import javascript
from ...hoster import host, HttpHoster, Matcher, urljoin

@host
class this:
    model = HttpHoster
    name = 'zippyshare.com'
    favicon_url = 'http://www.zippyshare.com/images/favicon.ico'
    patterns = [
        Matcher('https?', 'www(?P<host>\d*)\.zippyshare\.com', r'/v(?:/|iew.jsp.*key=)(?P<id>\d+)'),
    ]
    url_template = 'http://www{host}.zippyshare.com/v/{id}/file.html'

def on_check(file):
    resp = file.account.get(file.url)

    if ">File does not exist on this server</div>" in resp.text:
        file.set_offline()

    name = re.search(r'>Name:</font>\s*<font style="[^"]*">([^<]*)</font>', resp.text) or file.parse_error('filename')
    name = name.group(1)
    size = re.search(r'>Size:</font>\s*<font style="[^"]*">([^<]*)</font>', resp.text) or file.parse_error('filesize')
    size = size.group(1)

    file.set_infos(name=name, approx_size=size)

def on_download(chunk):
    resp = chunk.account.get(chunk.file.url)

    url = None

    m = re.search(r"<script type=\"text/javascript\">([^<]*?)document\.getElementById\('dlbutton'\)\.href = ([^;]+);", resp.text)
    if m:
        a, b = m.group(1), m.group(2)
        n = re.search(r'<span id="omg" class="(\d+)" style="display:none;">', resp.text)
        if n:
            a = a.replace("document.getElementById('omg').getAttribute('class');", n.group(1))
        js = "{}{}".format(a, b)
        url = javascript.execute(js)
        url = urljoin(chunk.file.url, url)
    else:
        m = re.search(r'swfobject\.embedSWF\("([^"]+)".*?seed: (\d+)', resp.text)
        if m:
            swf_url, file_seed = m.groups()
            raise NotImplementedError()

    if url is None:
        shortencode = re.search(r"shortencode: '([^']+)'", resp.text).group(1)
        url = re.search(r"document.location = '([^']+)'", resp.text).group(1)
        url = urljoin(chunk.file.url, url)

        for result, challenge in chunk.solve_captcha('recaptcha', parse=resp.text, retries=5):
            data = {'challenge': challenge, 'response': result, 'shortencode': shortencode}
            r = chunk.account.post('http://www{}.zippyshare.com/rest/captcha/test'.format(chunk.file.pmatch.host), data=data)
            if r.json():
                break
    return url


def on_initialize_account(account):
    account.get("http://zippyshare.com/?locale=en")
