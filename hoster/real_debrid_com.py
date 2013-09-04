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
    model = hoster.MultiHttpHoster
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
    
def on_download_premium(chunk):
    data = unrestrict(chunk.account, chunk.url)
    print data
    try:
        if data["error"]:
            chunk.fatal(data[u'message'])
    except KeyError:
        chunk.no_download_link()
    try:
        return data['main_link']
    except KeyError:
        chunk.no_download_link()

def on_initialize_account(account):
    print "real-debrid account init", account.username
    if not account.username:
        return
    payload = {
        "user": account.username,
        "pass": account.password,
    }
    resp = account.get("https://real-debrid.com/ajax/login.php", params=payload).json()
    if not (resp["error"] == 0 and resp["message"] == "OK" and resp["captcha"] == 0):
        print "real-debrid login failed:", resp
        account.premium = False
        return account.login_failed()

    resp = account.get("http://real-debrid.com/lib/api/account.php")
    
    account.premium = resp.soup.find("type").text == u"premium"
    if account.premium:
        print "real-debrid premium set"
        account.expires = resp.soup.find("expiration-txt").text
    else:
        print "real-debrid no premium account"
        print resp.text
        return
    resp = account.get("http://real-debrid.com/api/hosters.php")
    account.set_compatible_hosts(re.findall('"(.*?)"', resp.text))
    account._unrestricted = dict()

def unrestrict(account, url, clear=False):
    if clear:
        del account._unrestricted[url]
    try:
        return account._unrestricted[url]
    except KeyError:#
        v = account._unrestricted[url] = account.get("https://real-debrid.com/ajax/unrestrict.php?link="+url).json()
        return v

#http://www.real-debrid.com/api/regex.php?type=all incorporate somehow?
