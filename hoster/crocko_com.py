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
    name = 'crocko.com'
    patterns = [
        hoster.Matcher('https?', ['*.crocko.com', '*.easy-share.com'], '!/<id>')
    ]
    url_template = 'http://www.crocko.com/{id}'

def check_file_status(file, text):
    if "<h1>Sorry,<br />the page you're looking for <br />isn't here.</h1>" in text:
        file.set_offline()

    if "Requested file is deleted" in text:
        file.set_offline('file is deleted')

    m = re.search(r'<div class="msg-err">\s*<div class="inner">\s*<h4>([^<]*)</h4>\s*</div>\s*</div>', text, re.MULTILINE)
    if m:
        file.set_offline(m.group(1))

def on_check(file):
    resp = file.account.get(file.url, stream=True)
    if 'Content-Disposition' in resp.headers:
        name = hoster.contentdisposition.parse(resp.headers['Content-Disposition'])
        size = int(resp.headers['Content-Length'])
        file.set_infos(name=name, size=size)
    else:
        check_file_status(file, resp.text)

        m = re.search(r'<span class="fz24">Download:\s*<strong>(?P<name>[^<]*)</strong>\s*</span>\s*<span class="tip1"><span class="inner">(?P<size>[^<]*)</span></span>', resp.text, re.MULTILINE)
        if not m:
            file.set_offline('error parsing file infos. plugin out of date?')

        name = m.group('name').replace('<br>', '')
        size = m.group('size')
        file.set_infos(name=name, approx_size=size)

def on_download_premium(chunk):
    return chunk.url

def check_free_download_status(chunk, text):
    if "There is another download in progress from your IP" in text:
        chunk.account.ip_blocked(1800, need_reconnect=True)
    if 'Please wait or <a href="https://www.crocko.com/billing">click here</a> to buy premium' in text:
        chunk.temporary_unavailable(1800)
    if "There are no more download slots available right now" in text:
        chunk.temporary_unavailable(1800)
    if "You need Premium membership to download this file" in text:
        chunk.premium_needed()

def on_download_free(chunk):
    resp = chunk.account.get(chunk.file.url)

    check_file_status(chunk.file, resp.text)
    check_free_download_status(chunk, resp.text)

    wait = re.search(r"w='(\d+)'", resp.text)
    if wait:
        wait = time.time() + int(wait.group(1))

    s = BeautifulSoup(resp.text)
    form = s.select('#recaptcha_div')
    if not form:
        chunk.parse_error('captcha form')
    form = form[0].find_parent('form')
    url, data = hoster.serialize_html_form(form)
    url = hoster.urljoin(resp.url, url)

    for result, challenge in chunk.solve_captcha('recaptcha', parse=resp.text, retries=5):
        data["recaptcha_challenge_field"] = challenge
        data["recaptcha_response_field"] = result
        if wait and wait > time.time():
            chunk.wait(wait - time.time())
        resp = chunk.account.post(url, data=data, stream=True)
        if 'Content-Disposition' in resp.headers:
            return resp
        if "Entered code is invalid" in resp.text:
            continue
        check_free_download_status(chunk, resp.text)
        chunk.plugin_out_of_date()

def on_initialize_account(self):
    self.get("http://crocko.com/i18n/changeLang/?lang=en&url=Lw==")

    if not self.username:
        return
    
    data = {"login": self.username, "password": self.password, "remember": 1}
    self.post("http://www.crocko.com/accounts/login", data=data)

    if not "ACCOUNT" in self.cookies and not "PREMIUM" in self.cookies:
        self.login_failed()

    resp = self.get("http://www.crocko.com/accounts")

    if ">expired" in resp.text:
        self.premium = False
        return

    self.premium = re.search("Premium( (membership|account))?: <.*?>(Active)<", resp.text, re.IGNORECASE) and True or False
    if not self.premium:
        return

    expires = re.search(r"Ends:</span>.*?<span>(.*?)<", resp.text)
    if not expires:
        expires = re.search(r"End time:(.*?)<", resp.text)
    if not expires:
        expires = re.search(r"Starts:.*?Ends: (.*?)<", resp.text)
    if not expires:
        expires = re.search(r"Duration:(.*?)<", resp.text)
    if expires:
        expires = expires.group(1)
    expires = expires.strip()
    expires = re.sub(', in', '', expires)
    if not expires or expires == 'unlimited':
        self.expires = None
    else:
        self.expires = expires

    traffic = re.search(r"Traffic left:(.*?)<", resp.text)
    if traffic:
        self.traffic = traffic
