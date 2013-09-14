# encoding: utf-8
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

from ... import hoster

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'netload.in'
    patterns = [
        hoster.Matcher('https?', '*.netload.in', '!/datei<id>/<filename>.htm'),
    ]
    url_template = 'http://netload.in/datei{id}/{filename}.htm'

    max_filesize_free = hoster.GB(2)
    max_filesize_premium = hoster.GB(2)

    has_captcha_free = False
    max_download_speed_free = 300
    waiting_time_free = 1

def on_check(file):
    # http://api.netload.in/index.php?id=4
    payload = {
        "auth": apikey(file.account),
        "file_id": file.pmatch.id,
        "bz": "1",
        "md5": "1",
    }
    resp = file.account.post("http://api.netload.in/info.php", data=payload)
    try:
        fid, filename, filesize, status, md5 = resp.text.strip().split(";")
    except ValueError:
        if '403 - Forbidden' in resp.text:
            file.retry('website error', 2)
        raise
    if status == "offline":
        file.set_offline()
    file.set_infos(name=filename, size=int(filesize), hash_type='md5', hash_value=md5)
    
def _get_status(chunk, **kwargs):
    url = "http://netload.in/json/datei{}.htm".format(chunk.file.pmatch.id)
    kwargs["headers"] = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.3 Safari/537.36",
    }
    resp = chunk.account.get(url, **kwargs)
    return resp.json()
    
def _check_status(chunk):
    status = _get_status(chunk)
    status["state"] = status["state"].lower()
    if status["state"] == "failpass":
        def check_pw(result):
            newstatus = _get_status(chunk, params=dict(password=result))
            if newstatus["state"] != "failpass":
                status.update(newstatus)
                return True
            else:
                return False
        # xxx does not exist
        password = chunk.ask_for_password(check_pw, "File `{}` from `{}` requires a password:".format(chunk.file.name, "netload.in"))
        if password is False:
            return chunk.password_aborted()
        if not password:
            return chunk.password_invalid
    if status["state"] == "limitexceeded":
        return chunk.account.ip_blocked(status["countdown"])
    if status["state"] != "ok":
        return chunk.fatal("Not able to download: {}".format(status["state"]))
    if status["countdown"]:
        chunk.wait(status["countdown"])
    if not status["link"]:
        return chunk.fatal("Unknown Error")
    return status["link"]
    
def on_download_premium(chunk):
    return _check_status(chunk)

def on_download_free(chunk):
    return _check_status(chunk)


def on_initialize_account(self):
    self._apikey = "3xvDYiKC2l6XarLXj3mUMR1LudqXeMUY"

    if not self.username:
        self.get("http://netload.in/")
        return

    payload = {
        "txtuser": self.username,
        "txtpass": self.password,
        "txtcheck": "login",
        "txtlogin": "Login",
    }
    resp = self.post("http://netload.in/index.php", data=payload, allow_redirects=False)
    if not resp.headers["Location"] == "/index.php":
        self.fatal("Login failed.")
    else:
        self.browser.cookies.update(resp.cookies)

    resp = self.get("http://netload.in/index.php?id=2&lang=de")
    match = re.search(r"Verbleibender Zeitraum\<\/div\>.*?\<span.*?\>(.*?)\<\/span\>", resp.text, re.DOTALL)
    if match:
        premiumleft = match.group(1)
        if premiumleft == "Kein Premium":
            self.premium = False
        else:
            self.premium = True
            expire = time.time()
            factors = {"Jahre": 365*24*60*60, "Tage": 24*60*60, "Stunden": 60*60}
            for frame in premiumleft.split(", "):
                number, epo = frame.split(" ")
                expire += int(number) * factors[epo]
            self.expire = expire
    
def apikey(self):
    if self.username:
        # get a apikey for this account
        resp = self.get("http://www.netload.in/index.php?id=56&lang=de")
        match = re.search("Your Auth Code\: \<span.*?\>(.*?)\<\/span\>", resp.text, re.DOTALL)
        if match:
            self._apikey = match.group(1)
    return self._apikey
