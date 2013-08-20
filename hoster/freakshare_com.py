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

from ... import hoster, account

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'freakshare.com'
    favicon_url = 'http://freakshare.com/images/favicon.ico'
    patterns = [
        hoster.Matcher('https?', ['*.freakshare.com', '*.freakshare.net'], '!/files/<id>/<name>.htm'),
    ]
    url_template = 'http://freakshare.com/files/{id}/{name}.html'

def download_gateway_premium(ctx, text):
    did = re.search(r'<input type="hidden" value="(\d+)" name="did" />', text).group(1)
    data = {"section": "waitingtime", "did": did, "submit": "Download"}
    return ctx.account.post(ctx.url, data=data, stream=True)

def on_check(file):
    resp = file.account.get(file.url, stream=True)
    if 'Content-Disposition' in resp.headers:
        resp.close()
        name = hoster.contentdisposition.parse(resp.headers['Content-Disposition'])
        size = int(resp.headers['Content-Length'])
        file.set_infos(name=name, size=size)
        return

    if "We are back soon" in resp.text:
        file.temporary_unavailable(120)
    if "Sorry but this File is not avaible" in resp.text:
        file.set_offline()
    if "Sorry, this Download doesnt exist anymore" in resp.text:
        file.set_offline()
    if "This file does not exist!" in resp.text:
        file.set_offline()
    if "No Downloadserver. Please try again" in resp.text:
        file.temporary_unavailable(1800)
    if "Your Traffic is used up for today" in resp.text:
        name = file.pmatch.name
        file.set_infos(name=name)
        return

    if file.account.premium:
        resp = download_gateway_premium(file, resp.text)
        if 'Content-Disposition' in resp.headers:
            resp.close()
            name = hoster.contentdisposition.parse(resp.headers['Content-Disposition'])
            size = int(resp.headers['Content-Length'])
            file.set_infos(name=name, size=size)
            return

    name = re.search(r'"box_heading" style="text-align:center;">(.*?)- .*?</h1>', resp.text)
    if not name:
        file.parse_error('filename')
    name = name.group(1).strip()

    size = re.search(r'"box_heading" style="text-align:center;">.*?- (.*?)</h1>', resp.text)
    if size:
        size = size.group(1).replace('Byte', 'B')
    else:
        size = None

    file.set_infos(name=name, approx_size=size)

def on_download_premium(chunk):
    resp = chunk.account.get(chunk.url, chunk=chunk, stream=True)
    if 'Content-Disposition' in resp.headers:
        return resp
    resp.close()
    resp = download_gateway_premium(chunk, resp.text)
    if 'Content-Disposition' in resp.headers:
        return resp
    resp.close()
    chunk.no_download_link()

def on_download_free(chunk):
    resp = chunk.account.get(chunk.file.url)

    ajax_url = re.search(r'\$\.get\("(\.\./\.\..*?)",', resp.text)
    if ajax_url:
        ajax_url = hoster.urljoin(resp.url, ajax_url.group(1))

    s = BeautifulSoup(resp.text)
    form = s.select('#dlbutton')[0].find_parent('form')
    url, data = hoster.serialize_html_form(form)
    url = hoster.urljoin(resp.url, url)

    if ajax_url:
        r = chunk.account.get(ajax_url, headers={"X-Requested-With": "XMLHttpRequest"})
        wait = re.search("SUCCESS:(\d+)", r.text)
    else:
        wait = re.search("var time = (\d+)\.0", resp.text)
    if wait:
        wait = int(wait.group(1))
        if wait > 600:
            chunk.account.ip_blocked(wait, need_reconnect=True)
        else:
            chunk.wait(wait)

    resp = chunk.account.post(url, data=data, referer=resp.url, stream=True)
    if "Content-Disposition" in resp.text:
        return resp
    
    for result, challenge in chunk.solve_captcha('recaptcha', parse=resp.text):
        did = re.search(r'<input type="hidden" value="(\d+)" name="did" />', resp.text).group(1)
        data = {"recaptcha_challenge_field": challenge, "recaptcha_response_field": result, "section": "waitingtime", "did": did}
        r = chunk.account.post(url, data=data, referer=resp.url, stream=True)

        if "Content-Disposition" in r.headers:
            return r

        if "Sorry, you cant download more then" in r.text:
            chunk.only_one_connection_allowed(600, need_reconnect=True)

        if "Wrong Captcha" in r.text:
            this.log.info('wrong captcha')

def on_initialize_account(self):
    self.get("http://freakshare.com/index.php?language=EN", allow_redirects=False)

    if not self.username:
        return

    data = {"submit": "Login", "user": self.username, "pass": self.password}
    resp = self.post("http://freakshare.com/login.html", data=data)

    if "Wrong Username or Password!" in resp.text:
        self.login_failed()

    type = re.search(r"Accounttype:</td>\s*<td><b>(.*?)</b></td>", resp.text, re.MULTILINE).group(1)
    self.premium = 'premium' in type and True or False
    if self.premium:
        self.expires = re.search(r"valid until:</td>\s*<td><b>([0-9 \-:.]+)</b></td>", resp.text, re.MULTILINE).group(1)
        self.traffic = re.search(r"Traffic left:</td>\s*<td>([^<]+)", resp.text).group(1)
        self.premium = self.expires > time.time() and True or False
