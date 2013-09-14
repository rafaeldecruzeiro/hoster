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
import hashlib

from ... import hoster, javascript
from ...plugintools import between

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'hotfile.com'
    favicon_url = 'http://hotfile.com/images/other/favicon.ico'
    patterns = [
        hoster.Matcher('https?', '*.hotfile.com', '!/dl/<id1>/<id2>'),
    ]
    url_template = 'http://www.hotfile.com/dl/{id1}/{id2}/'

def on_check(file):
    data = {"action": "checklinks", "links": file.url, "fields": "id,status,name,size,sha1"}
    resp = file.account.post("http://api.hotfile.com/", data=data)

    line = resp.text.splitlines()[0]
    id, status, name, size, sha1 = line.split(',')
    status = int(status)
    size = int(size)

    if status not in (1, 2):
        file.set_offline()

    file.set_infos(name=name, size=size, hash_type='sha1', hash_value=sha1)

def on_download_premium(chunk):
    resp = call_api(chunk.account, 'getdirectdownloadlink', {'link': chunk.file.url})
    return resp.text.strip()

def on_download_free(chunk):
    resp = chunk.account.get(chunk.file.url)

    if "File is removed" in resp.text:
        chunk.set_offline()

    wait = re.findall(r"timerend=d\.getTime\(\)\+(\d+);", resp.text)
    if wait:
        wait = (sum([int(w) for w in wait])/1000 + 1) or 60
        if wait > 300:
            chunk.retry('waiting for download', wait, need_reconnect=True)
        chunk.wait(wait)
    #else:
    #    chunk.fatal('error getting wait time. plugin out of date?')
    
    for i in range(5):
        url = re.search(r'<td><a href="([^"]+)" class="click_download">Click here to download</a></td>', resp.text)
        if not url:
            payload = dict(re.findall("<input type=hidden name=(.*?) value=(.*?)>", resp.text))
            s1 = resp.content.find("function calcchecksum(){")
            if s1 == -1:
                chunk.no_download_link()
                return
                
            s2 = resp.content.find("}", s1)
            calcchecksum = resp.content[s1:s2+1] + " calcchecksum();"
            fieldname = between(resp.text, 'el.name = "', '"')
            fieldvalue = between(resp.text, 'el.value = "', "-")
            payload[fieldname] = "{}-{}".format(fieldvalue, javascript.execute(calcchecksum))
             
            if not payload:
                chunk.no_download_link()
            resp = chunk.account.post(chunk.file.url, data=payload, params="lang=en")
            continue
            
        resp = chunk.account.get(url.group(1), referer=resp.url, stream=True)
        if 'Content-Disposition' in resp.headers:
            return resp
        chunk.wait(10)

    chunk.no_download_link()


def call_api(account, method, data=None):
    if not data:
        data = dict()

    digest = account.post("http://api.hotfile.com/", data={"action": "getdigest"}).text
    pwhash = hashlib.md5(hashlib.md5(account.password).hexdigest() + digest).hexdigest()
    
    data['action'] = method
    data.update({"username": account.username, "passwordmd5dig": pwhash, "digest": digest})
    resp = account.post("http://api.hotfile.com/", data=data)
    return resp

def on_initialize_account(self):
    self.get("http://hotfile.com/?lang=en")

    if not self.username:
        return

    data = {"returnto": "/", "user": self.username, "pass": self.password}
    resp = self.post("http://hotfile.com/login.php", data=data)
    if "Bad username/password" in resp.text:
        self.login_failed()

    resp = call_api(self, 'getuserinfo')
    if resp.text.startswith('.'):
        self.fatal(resp.text[1:].strip())

    info = {}
    for p in resp.text.split("&"):
        key, value = p.split("=")
        info[key] = value

    if info['is_premium'] == '1':
        self.premium = True
        self.expires = info["premium_until"]

    elif info['is_premium'] == '0':
        self.premium = False
