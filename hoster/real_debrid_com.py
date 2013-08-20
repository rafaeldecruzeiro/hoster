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
    name = "real-debrid.com"
    model = hoster.MultiHttpPremiumHoster
    favicon_url = 'https://cdn.real-debrid.com/0098/images/favicon.ico'
    
    can_resume = True
    max_chunks = 1
    
def error(data, file):
    if data["error"] != 0:
        file.fatal(data.get("message", "Unknown error").encode("utf8"))

def on_check(file):
    data = unrestrict(file.account, file.url)
    error(data, file)
    file.set_infos(name=data["file_name"], size=int(data["file_size_bytes"]))
    
def on_download(chunk):
    data = unrestrict(chunk.account, chunk.url)
    for i in xrange(5):
        error(data, chunk)
        resp = chunk.account.get(data["main_link"], chunk=chunk, stream=True)
        if not resp.ok:
            data = unrestrict(chunk.account, chunk.url, True)
        else:
            return resp
    chunk.no_download_link()
    

def on_initialize_account(self):
    if not self.username:
        return
        
    payload = {
        "user": self.username,
        "pass": self.password,
    }
    resp = self.get("https://real-debrid.com/ajax/login.php", params=payload).json()
    if not (resp["error"] == 0 and resp["message"] == "OK" and resp["captcha"] == 0):
        self.premium = False
        return self.login_failed()

    self.premium = True
    resp = self.get("http://real-debrid.com/api/hosters.php")
    self.set_compatible_hosts(re.findall('"(.*?)"', resp.text))
    self._unrestricted = dict()

def unrestrict(account, url, clear=False):
    if clear:
        del account._unrestricted[url]
    try:
        return account._unrestricted[url]
    except KeyError:#
        v = account._unrestricted[url] = account.get("https://real-debrid.com/ajax/unrestrict.php?link="+url).json()
        return v

#http://www.real-debrid.com/api/regex.php?type=all incorporate somehow?
