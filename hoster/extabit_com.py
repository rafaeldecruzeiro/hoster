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
import random

from ... import hoster

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'extabit.com'
    patterns = [
        hoster.Matcher('https?', '*.extabit.com', '!/file/<id>'),
        hoster.Matcher('https?', '*.extabit.com', '!/go/<id>'),
    ]
    url_template = 'http://extabit.com/file/{id}'

def on_check(file):
    resp = file.account.get(file.url)

    if "File not found" in resp.text or "Such file doesn't exsist" in resp.text:
        file.set_offline()

    name = re.search(r"<title>(.*?)download Extabit.com \- file hosting</title>", resp.text)
    if not name:
        name = re.search(r"download_filename\".*?>(.*?)</div", resp.text)
    if not name:
        name = re.search(r"extabit\.com/file/.*?'>(.*?)</a>", resp.text)
    if not name:
        file.set_offline('file not found (error parsing name)')
    name = name.group(1)

    if name.startswith("file "):
        m = re.search(r"df_html_link\" name=\"df_html_link\" class.*?>(.*?)</", resp.text)
        if m:
            m = m.group(1)
            if len(m) > len(name):
                name = m

    size = re.search(r"Size: ([^<>\"]*?)</div>", resp.text, re.MULTILINE)
    if not size:
        size = re.search(r"class=\"download_filesize(_en)\">.*?\[(.*?)\]", resp.text, re.MULTILINE)
    if not size:
        size = re.search(r'Size:</th>\s*<td class="col-fileinfo">(.*?)</', resp.text, re.MULTILINE)
    if not size:
        file.set_offline('file not found (error parsing size)')
    size = size.group(1).upper()

    file.set_infos(name=name.strip(), approx_size=size)

def on_download_premium(chunk):
    resp = chunk.account.get(chunk.file.url, stream=True, chunk=chunk)
    if not 'Content-Disposition' in resp.headers:
        if " is temporary unavailable" in resp.text or "No download mirror" in resp.text:
            chunk.temporary_unavailable(1800)
        m = re.search(r'<div id="download_filename" class="df_archive">[^<]*</div>\s*<a href="(http://.*?)"', resp.text)
        if not m:
            m = re.search(r'"(http://[a-z]+\d+\.extabit\.com/[a-z0-9]+/.*?)"', resp.text)
        if not m:
            chunk.no_download_link()
        resp = chunk.account.get(m.group(1), stream=True, referer=resp.url, chunk=chunk)
        if not 'Content-Disposition' in resp.headers:
            chunk.fatal('error starting download. plugin out of date?')
    return resp

def on_download_free(chunk):
    resp = chunk.account.get(chunk.file.url)

    if ">Only premium users can download this file" in resp.text or "<h2>The file that you're trying to download is larger than" in resp.text:
        chunk.premium_needed()

    if " is temporary unavailable" in resp.text or "No download mirror" in resp.text:
        chunk.temporary_unavailable(1800)

    m = re.search(r"Next free download from your ip will be available in <b>(\d+)\s*minutes", resp.text)
    if m:
        chunk.wait(int(m.group(1)) * 60)
    elif "The daily downloads limit from your IP is exceeded" in resp.text:
        chunk.account.ip_blocked(3600, need_reconnect=True)

    url = chunk.file.url

    for result, challenge in chunk.solve_captcha('recaptcha', parse=resp.text, retries=5):
        params = {"type": "recaptcha", "challenge": challenge, "capture": result}
        r = chunk.account.get(chunk.file.url, params=params)
        j = r.json()
        if "ok" in j and j['ok']:
            if 'href' in j:
                url = "{}{}".format(chunk.file.url, j['href'])
                break
                
    resp = chunk.account.get(url)
    m = re.search('Turn your download manager off and[ ]+<a href="(http.*?)"', resp.text)
    if not m:
        m = re.search(r'"(http://guest\d+\.extabit\.com/[a-z0-9]+/.*?)"', resp.text)
    if not m:
        chunk.no_download_link()

    return m.group(1)

def on_initialize_account(self):
    self.get("http://extabit.com/language.jsp?lang=en")

    if not self.username:
        return

    data = {"email": self.username, "pass": self.password, "remember": 1, "auth_submit_login.x": random.randint(0, 10), "auth_submit_login.y": random.randint(0, 10), "auth_submit_login": "Enter"}
    self.post("http://extabit.com/login.jsp", data=data, allow_redirects=False)

    if not "auth_uid" in self.browser.cookies or not "auth_hash" in self.browser.cookies:
        self.login_failed()

    resp = self.get("http://extabit.com/")
    m = re.search(r"Premium is active till <span class=\"green\"><strong>(.*?)</strong>", resp.text)
    if not m:
        m = re.search(r"Premium is active till ([\d\.]+) ", resp.text)
    if not m:
        m = re.search(r"Storage valid until (\d{2}\.\d{2}\.\d{4})", resp.text)
    if m:
        self.expires = m.group(1)
        self.premium = True
    else:
        self.premium = False
