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

import re, time, urlparse
from ... import hoster

@hoster.host
class this:
    name = "alldebrid.com"
    model = hoster.MultiHttpHoster
    favicon_url = 'http://cdn.alldebrid.com/lib/images/default/favicon.png'
    
    can_resume = True
    max_chunks = 1

def on_check(file):
    link = unrestrict(file, file.url)
    name = None
    try:
        name = urlparse.unquote(link.rsplit("/", 1)[1])
    except IndexError:
        pass
    hoster.check_download_url(file, link, name=name)
    
def on_download_premium(chunk):
    return unrestrict(chunk.file, chunk.url)

def api(account, action, **kwargs):
    kwargs["action"] = action
    return account.get("http://www.alldebrid.com/api.php", params=kwargs)

def on_initialize_account(account):
    if not account.username:
        return
    
    login = api(account, "info_user", login=account.username, pw=account.password)
    try:
        account.premium = login.soup.find("type").text == u"premium"
    except AttributeError:
        print login.text
        account.fatal(login.text)
        return
    
    if not account.premium:
        return
    account.expires = time.time() + int(login.soup.find("date").text) * 86400
    
    resp = api(account, "get_host")
    account.set_compatible_hosts(re.findall('"(.*?)"', resp.text))
    account._unrestricted = dict()

def unrestrict(file, url, clear=False):
    account = file.account
    if clear:
        del account._unrestricted[url]
    try:
        return account._unrestricted[url]
    except KeyError:
        payload = {
            "pseudo": account.username,
            "password": account.password,
            "link": url,
            "view": 1,
            "json": "true",
        }
        resp = account.get("http://www.alldebrid.com/service.php", params=payload)
        resp.raise_for_status()
        link = resp.text
        if not link.startswith("http"):
            error = resp.json()["error"]
            if "Hoster unsupported or under maintenance." in error:
                file.retry(error, 3600)
            elif "_limit" in error:
                file.retry(u"Limit reached. " + error, 1800)
            else:
                file.fatal(error)
        v = account._unrestricted[url] = link
        return v