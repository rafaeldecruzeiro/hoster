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
import time

from bs4 import BeautifulSoup

from ... import hoster

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'shareflare.net'
    uses = 'letitbit.net'
    patterns = [
        hoster.Matcher('https?', '*.shareflare.net', '!/download/<id>/<filename>.html'),
    ]
    max_filesize_free = hoster.GB(2)
    max_filesize_premium = hoster.GB(2)

def on_download_free(chunk):
    resp = chunk.account.get(chunk.file.url)
    if 'onclick="checkCaptcha()" style="' in resp.text:
        chunk.fatal('file seems to be offline')

    s = BeautifulSoup(resp.text)
    form = s.select('#dvifree')[0]
    url, result = hoster.serialize_html_form(form)
    url = hoster.urljoin(resp.url, url)
    resp = chunk.account.post(url, data=result)
    s = BeautifulSoup(resp.text)
    form = s.select('#dvifree')
    if form:
        url, result = hoster.serialize_html_form(form[0])
        url = hoster.urljoin(resp.url, url)
        resp = chunk.account.post(url, data=result)

    url = re.search(r'\$\.post\("(/ajax/check_[^<>"]*)"', resp.text, re.MULTILINE)
    if not url:
        chunk.parse_error('download url')
    url = hoster.urljoin(resp.url, url.group(1))

    wait = re.search(r'id="seconds" style="font-size:18px">(\d+)</span>', resp.text)
    if not wait:
        wait = re.search(r'"seconds = (\d+)"', resp.text)
    if wait:
        wait = time.time() + int(wait.group(1))

    if "recaptcha" in resp.text:
        control = re.search(r"var recaptcha_control_field = '([^<>\"]*?)'", resp.text).group(1)
        for result, challenge in chunk.solve_captcha('recaptcha', parse=resp.text, retries=5):
            if wait and wait > time.time():
                chunk.wait(wait - time.time())
            data = {"recaptcha_challenge_field": challenge, "recaptcha_response_field": result, "recaptcha_control_field": control}
            r = chunk.account.post(url, data=data, referer=resp.url, headers={"X-Requested-With": "XMLHttpRequest"})
            if len(r.text) < 2 or "error_wrong_captcha" in r.text:
                continue
            if "error_free_download_blocked" in r.text:
                chunk.account.ip_blocked(3*3600, need_reconnect=True)
            if "callback_file_unavailable" in r.text:
                chunk.temporary_unavailable(1800)
            if r.text.startswith("http"):
                return r.text
            else:
                chunk.plugin_out_of_date(msg="")
    else:
        chunk.plugin_out_of_date(msg='no known captcha method found')
    
def on_initialize_account(self):
    self.account_checked = True

    self.set_user_agent()
    self.cookies["lang"] = "en"
    if not self.username:
        return
    payload = {
        "login": self.username,
        "password": self.password,
        "act": "login",
    }
    resp = self.post("http://shareflare.net/", data=payload)
    check = self.cookies.get("log")
    if not check:
        check = self.cookies.get("pas")
    if not check:
        self.login_failed()
    
    resp = self.post("http://shareflare.net/ajax/get_attached_passwords.php", data="act=get_attached_passwords")
    traffic = re.search("<td>(\\d+\\.\\d+)</td>", resp.text)
    expire = re.search("<td>(\\d{4}\\-\\d{2}\\-\\d{2})</td>", resp.text)
    if traffic and expire:
        self.premium = True
        self.traffic = hoster.GB(float(traffic.group(1)))
        self.expire = time.mktime(time.strptime(expire.group(1), "%Y-%m-%d"))
    else:
        self.premium = False
