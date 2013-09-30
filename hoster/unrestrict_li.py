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
    name = "unrestrict.li"
    model = hoster.MultiHttpHoster
    
    can_resume = True
    max_chunks = 1

def error(data, file):
    errmsg = data.get("invalid")
    errcode = data.get("jd_error")
    if not errmsg:
        return
    if "Expired session" in errmsg or \
            ("You are not allowed to download from this host" in errmsg and file.account.premium):
        file.account.reboot()
        file.retry("login", 10)
    elif "daily limit" in errmsg:
        file.retry("Daily limit reached", 3600)
    elif "ERROR_HOSTER_TEMPORARILY_UNAVAILABLE" == errcode:
        file.retry("Hoster is temporarily unavailable", 600)
    elif "File offline" in errmsg:
        file.set_offline()
    else:
        file.fatal(errmsg)

def on_check(file):
    _, data = unrestrict(file.account, file.url).values()[0]
    error(data, file)
    file.set_infos(name=data["name"], size=int(data["size"]))
    
def on_download_premium(chunk):
    link, data = unrestrict(chunk.account, chunk.url)
    print data
    error(data, chunk)
    return link

def on_initialize_account(account):
    if not account.username:
        return
    account.set_user_agent()
    account.cookies["lang"] = "EN"
    payload = {
        "username": account.username,
        "password": account.password,
        "return": "home",
        "signin": "Login",
    }
    account.get("https://unrestrict.li/sign_in")
    resp = account.post("https://unrestrict.li/sign_in", data=payload)
    resp2 = account.get("https://unrestrict.li/api/jdownloader/user.php?format=json")
    result = resp2.json()["result"]
    if not result.get("vip", 1):
        print "VIP is 0", resp2.request.headers, resp2.headers
        return account.login_failed()

    account.expires = result["expires"]
    account.traffic = result["traffic"]
    account.premium = True

    resp = account.get("https://unrestrict.li/api/jdownloader/hosts.php")
    hosts = re.findall("<host>(.*?)</host>", resp.content)
    account.set_compatible_hosts(list(set(hosts) - {"youtube.com", "mega.co.nz", "youtu.be"}))
    account._unrestricted = dict()

def unrestrict(account, url, clear=False):
    if clear:
        del account._unrestricted[url]
    try:
        return account._unrestricted[url]
    except KeyError:
        v = account._unrestricted[url] = account.post(
            "https://unrestrict.li/unrestrict.php",
            data=dict(link=url, domain="long")
        ).json().items()[0]
        return v
