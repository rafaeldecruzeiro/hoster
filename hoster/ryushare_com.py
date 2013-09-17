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

from ... import hoster
from ...plugintools import between

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'ryushare.com'
    uses = 'junocloud.me'
    patterns = [
        hoster.Matcher('https?', ['*.ryushare.com'], '!/<id>/<name>'),
    ]
    max_filesize_free = hoster.GB(2)
    max_filesize_premium = hoster.GB(2)

    login_url = "http://ryushare.com/login.python"
    account_url = "http://ryushare.com/my-account.python"

def on_check_http(file, resp):
    file.set_infos(name=file.pmatch.name)
    content = resp.soup.find("div", attrs={"id": "content"})
    if file.account.premium:
        t = content.find("table", attrs={"class": "file_slot"})
        if not t:
            error = content.find("b").text
            if error == "File not Found":
                file.set_offline()
            else:
                file.fatal(error)
            return
        name = t.find("td", attrs={"nowrap": "nowrap"}).text
        size = between(t.find("small").text, "(", ")")
        file.set_infos(name=name, size=size.split(" ")[0])
    else:
        name = content.find("h2").text.strip().replace("Download File", "").strip()
        size = between(content.find("font").text, "(", ")").strip()
        file.set_infos(name=name, approx_size=size)

def on_download_premium(chunk):
    resp = chunk.account.get(chunk.url, allow_redirect=False)
    if "Location" in resp.headers:
        return resp.headers["Location"]
    _, payload = hoster.serialize_html_form(resp.soup.find(attrs={"name": "F1"}))
    payload["down_direct"] = 1
    resp = chunk.account.post(chunk.url, data=payload)
    return resp.soup.find("div", attrs={"id": "content"}).find("a")["href"]

def on_download_free(chunk):
    raise NotImplementedError("blocked by keycaptcha support for now.")
    resp = chunk.account.get(chunk.url)
    payload = hoster.serialize_html_form(resp.soup.find_all("form")[-1])
    resp = chunk.account.post(chunk.url, data=payload)

def on_initialize_account(account):
    resp = this.boot_account(account)
    if resp:
        f = resp.soup.find("form")
        ex = f.findAll("tr")[1]
        td = ex.findAll("td")
        if td[0].text.startswith("Premium account expire"):
            account.premium = True
            account.expire = td[1].text
        else:
            account.premium = False
