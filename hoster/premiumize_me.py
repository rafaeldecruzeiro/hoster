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

from ... import hoster

# https://secure.premiumize.me/?show=api

@hoster.host
class this:
    name = "premiumize.me"
    model = hoster.MultiHttpHoster
    can_resume = True
    max_chunks = 1

def on_check(file):
    result = api(file.account, "directdownloadlink", file, link=file.url)
    if result["filename"] and result["filesize"]:
        return file.set_infos(name=result["filename"], size=result["filesize"])
    resp = file.account.browser.head(result["location"])
    name, size, file.can_resume = hoster.http_response(file, resp)
    file.set_infos(name=name, size=size)

def on_download_premium(chunk):
    result = api(chunk.account, "directdownloadlink", chunk, link=chunk.url)
    try:
        return result["location"]
    except KeyError:
        chunk.no_download_link()
    
def api(account, method, chunk=None, **data):
    payload = {
        "method": method,
        "params[login]": account.username,
        "params[pass]": account.password,
    }
    for k, v in data.iteritems():
        payload["params[{}]".format(k)] = v
    data = account.get("https://api.premiumize.me/pm-api/v1.php", params=payload).json()
    result = data["result"]
    status = data["status"]
    message = data["statusmessage"]
    if status in {400, 403, 404}:
        account.fatal(message)
    elif status == 401:
        account.premium = False
        account.login_failed()
    elif status == 402:
        account.premium = False
        account.fatal(message)
    elif status in {502, 503, 509}:
        chunk.retry(3*60)
    return result
    
def on_initialize_account(account):
    if not account.username:
        return
    result = api(account, "accountstatus")
    account.premium = result["type"] != "free"
    account.expires = result["expires"]
    account.traffic = int(result["fairuse_left"] * 100) # in percent
    account.traffic_max = 100
    hosterlist = api(account, "hosterlist")
    tlds = set()
    for i in hosterlist["hosters"].itervalues():
        tlds |= set(i["tlds"])
    account.set_compatible_hosts(list(tlds))
    
