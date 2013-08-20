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

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'datafile.com'
    patterns = [
        hoster.Matcher('https?', '*.datafile.com', '!/d/<id>')
    ]
    url_template = 'http://www.datafile.com/d/{id}'

def on_initialize_account(account):
    account.cookies['lang'] = 'en'
    account.set_user_agent('windows')
    if not account.username:
        return
    data = {
        "login": account.username,
        "password": account.password,
        "remember_me": "1",
        "btn": ""
    }
    resp = account.post("https://www.datafile.com/login.html", data=data, allow_redirects=False)
    if 'user' not in resp.cookies or 'hash' not in resp.cookies:
        account.login_failed()
    resp = account.get("https://www.datafile.com/profile.html")
    expires = resp.soup.find('table', 'prof-table-form').find('tr').find('td', 'el').text.strip()
    if 'No data' in expires:
        account.premium = False
    else:
        account.expires = expires

def on_check(file):
    resp = file.account.get(file.url, use_cache=True)
    error = resp.soup.find('div', 'error-msg')
    if error:
        error = re.sub('\s*ErrorCode \d+: ', '', error.text, re.DOTALL).strip()
        file.set_offline(error)

    name = resp.soup.find('div', 'file-name').text.strip()
    size = resp.soup.find('div', 'file-size').find('span').text.strip()
    file.set_infos(name=name, size=size)

def on_download_free(chunk):
    resp = chunk.account.get(chunk.url, use_cache=True)
    # TODO: check premium needed

    wait = resp.soup.find('div', 'counter').find('span', 'time').text.strip()
    wait = hoster.parse_seconds(wait)
    if wait > 610:
        chunk.ip_blocked(seconds=wait)
    wait += time.time()

    for result, challenge in chunk.solve_captcha('recaptcha', parse=resp.text, retries=5):
        if wait > time.time():
            chunk.wait(wait - time.time())
        data = {
            "doaction": "getFileDownloadLink",
            "recaptcha_challenge_field": challenge,
            "recaptcha_response_field": result,
            "fileid": chunk.pmatch.id}
        resp = chunk.account.post('https://www.datafile.com/files/ajax.html', data=data)
        j = resp.json()
        if j['success']:
            return j['link']

def on_download_premium(chunk):
    resp = chunk.account.get(chunk.url, chunk=chunk, stream=True)
    if 'Content-Disposition' not in resp.headers:
        resp.close()
        chunk.no_download_link()
    return resp
