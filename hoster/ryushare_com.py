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

    url_template = 'http://ryushare.com/{id}'

    login_url = "http://ryushare.com/login.python"
    account_url = "http://ryushare.com/my-account.python"

def check_errors(ctx, resp):
    if 'The file you were looking for could not be found' in resp.text:
        ctx.set_offline()
    if 'Sorry! User who was uploaded this file requires premium to download.' in resp.text:
        ctx.premium_needed()
    if 'You have reached the download-limit' in resp.text:
        ctx.ip_blocked(1800)

def on_check_http(file, resp):
    check_errors(file, resp)
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
    check_errors(chunk, resp)
    if "Location" in resp.headers:
        return resp.headers["Location"]
    submit, data = hoster.xfilesharing_download(resp, 2, False)
    data["down_direct"] = 1
    resp = submit()
    return resp.soup.find("div", attrs={"id": "content"}).find("a")["href"]

def on_download_free(chunk):
    resp = chunk.account.get(chunk.url)
    check_errors(chunk, resp)
    resp = hoster.xfilesharing_download(resp, 1)[0]()
    check_errors(chunk, resp)

    ctx = dict()

    def get_form(kwargs):
        err = resp.soup.find('div', attrs={'class': 'err'})
        if err:
            m = re.match(r'You have to wait (.*?) till next download', err.text)
            if m:
                chunk.account.ip_blocked(hoster.parse_seconds2(m.group(1)))
            chunk.retry(err.text.strip(), 1800)
        ctx['wait'] = resp.soup.find(attrs={'id': 'countdown_str'}).text.replace('Please wait', '').strip()
        ctx['wait'] = hoster.parse_seconds2(ctx['wait']) + time.time()

        ctx['submit'], ctx['data'] = hoster.xfilesharing_download(resp, 2)
        kwargs['challenge_id'] = re.search(r'http://api\.solvemedia\.com/papi/challenge\.script\?k=(.*?)"', resp.text).group(1)

    for result, challenge in chunk.solve_captcha('solvemedia', prefunc=get_form, retries=5):
        ctx['data']['adcopy_challenge'] = challenge
        ctx['data']['adcopy_response'] = result
        if ctx['wait'] and time.time() < ctx['wait']:
            chunk.wait(ctx['wait'] - time.time())
        resp = ctx['submit']()
        if '<div class="err">WRONG CAPTCHA</div>' in resp.text:
            continue
        return resp.soup.find('a', href=lambda a: 'free' in a, text=lambda a: a == 'Click here to download').get('href')

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
