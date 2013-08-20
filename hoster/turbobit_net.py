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
import urlparse

import bs4

from ... import hoster, input
from ...plugintools import between

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'turbobit.net'
    favicon_url = 'http://turbobit.net/favicon/fd1.ico'
    patterns = [
        hoster.Matcher('https?', '*.turbobit.net', '!/<id>.html'),
        hoster.Matcher('https?', '*.turbobit.net', '!/<id>/<filename>.html'),
    ]
    url_template = 'http://turbobit.net/{id}.html'
    max_filesize_free = hoster.GB(1)
    max_filesize_premium = hoster.GB(2)

def on_check(file):
    data = file.account.post("http://turbobit.net/linkchecker/check", data=dict(links_to_check=file.url))
    data = re.findall("<tr>.*?<td>(.*?)</td>.*?<td>(.*?)</td>.*?<td.*?/img/icon/(.*?).png.*</tr>", data.content, re.DOTALL)
    if not data:
        file.no_download_link()
    id, name, status = data[0]
    if status != "done":
        file.set_offline()
    file.set_infos(name=name)

def on_download_premium(chunk):
    resp = chunk.account.get(chunk.file.url)
    resp.raise_for_status()
    link = re.search("\\<span\\ class\\=\\'shorturl\\-link\\'\\>\\<input\\ type\\=\\'text\\'\\ value\\=\\'(.*?)\\'\\>\\<\\/span\\>", resp.text)
    if not link:
        chunk.no_download_link()
    link = link.group(1)
    return run_download(chunk, link)

def run_download(chunk, link):
    if not link.startswith("http"):
        link = "http://turbobit.net" + link
    resp = chunk.account.get(link, allow_redirects=False)
    link = resp.headers["location"]
    try:
        md5 = urlparse.parse_qs(link)["md5"][0]
    except KeyError:
        pass
    else:
        chunk.file.set_infos(hash_type="md5", hash_value=md5)
    return link
    
def parse_captcha(c, text, **_):
    form = bs4.BeautifulSoup(text()).find("form", action="#")
    if form is None:
        c.parse_error('captcha form', 60)
    payload = {i.get("name"): i.get("value") for i in form.findAll("input")}
    if payload["captcha_type"] == "recaptcha":
        raise NotImplementedError
    img = form.find("img", alt="Captcha").get("src")
    imgdata = c.account.get(img)
    payload["captcha_response"] = input.captcha_text(imgdata.content, imgdata.headers["content-type"], "captcha turbobit.net").upper()
    return payload

def on_download_free(chunk):
    id = chunk.file.pmatch.id
    freeurl = "http://turbobit.net/download/free/" + id
    resp = chunk.account.get(freeurl)
    if "From your IP range the limit of connections is reached" in resp.text:
        chunk.account.no_more_free_traffic(600, need_reconnect=True)
    m = re.search("try downloading again after <span id='timeout'>(\d+)</span>", resp.text)
    if m:
        chunk.ip_blocked(int(m.group(1)))
    for payload in chunk.iter_input("captcha", func=parse_captcha, c=chunk, text=lambda: resp.text, retries=5):
        resp = chunk.account.post(freeurl, data=payload)
        soup = bs4.BeautifulSoup(resp.text)
        if soup.find("div", **{"class": "captcha-error"}) is None:
            break
    size = between(soup.find("h1", **{"class": "download-file"}).text, "(", ")")
    chunk.file.set_infos(approx_size=size.replace(",", ".")[:-1])
    chunk.wait(70)
    headers = {
        "Accept": "text/html, */*",
        "Referer": freeurl,
        "X-Requested-With": "XMLHttpRequest",
    }
    resp = chunk.account.get("http://turbobit.net/download/getLinkTimeout/" + id, headers=headers)
    soup = bs4.BeautifulSoup(resp.text).find("a", id="popunder2")
    if not soup:
        chunk.no_download_link()
    link = soup["href"]
    return run_download(chunk, link)
     

def on_initialize_account(self):
    self.set_user_agent()
    self.cookies["user_lang"] = "en"
    if not self.username:
        self.premium = False
        return
    payload = {
        "user[login]": self.username,
        "user[pass]": self.password,
        "user[submit]": "Login",
    }
    login = self.post("http://turbobit.net/user/login", data=payload)
    if not '<div class="menu-item user-name">' in login.text:
        return self.login_failed()
    
    data = self.get("http://turbobit.net/")
    premium = re.search('<u>Turbo Access</u> to ([0-9.]+)', data.text)
    if premium:
        self.premium = True
        self.expires = time.mktime(time.strptime(premium.group(1), "%d.%m.%Y"))
    else:
        self.premium = False
