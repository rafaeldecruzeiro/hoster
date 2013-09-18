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
    name = 'junocloud.me'
    patterns = [
        hoster.Matcher('https?', '*.junocloud.me', '!/<id>'),
    ]
    max_filesize_free = hoster.GB(2)
    max_filesize_premium = hoster.GB(2)

    url_template = 'http://junocloud.me/{id}'

    login_url = 'http://junocloud.me/login.html'
    account_url = 'http://junocloud.me/account.html'

def boot_account(account):
    account.set_user_agent()
    account.cookies["lang"] = "english"
    if account.username is None:
        return
    
    data = {
        'op': 'login',
        'redirect': this.account_url,
        'login': account.username,
        'password': account.password,
        'loginFormSubmit': 'Login',
    }
    resp = account.post(this.login_url, data=data)
    if resp.url != this.account_url:
        account.login_failed()
        return
    return resp

def on_initialize_account(account):
    resp = boot_account(account)
    if resp:
        status = resp.soup.find('div', text=lambda a: 'Status:' in a if a else False).find_next('div').find('strong').text.strip()
        if status != 'Premium':
            account.premium = False
            return
        raise NotImplementedError('premium is not implemented')

def check_errors(ctx, resp):
    if 'The origin web server timed out responding to this request.' in resp.text:
        ctx.maintenance(180)
    h1 = resp.soup.find('h1')
    if h1:
        if 'File Not Found' in h1.text or '404 Not Found' in h1.text:
            ctx.set_offline()

def on_check_http(file, resp):
    check_errors(file, resp)
    name = resp.soup.find('input', attrs={'name': 'fname'}).get('value').strip()
    size = resp.soup.find('p', 'request_filesize').text.strip().split(' ', 1)[1].strip()
    file.set_infos(name=name, size=size)

def on_download_premium(chunk):
    raise NotImplementedError('premium is untested')

def on_download_free(chunk):
    resp = chunk.account.get(chunk.url, use_cache=True)
    check_errors(chunk, resp)
    resp = hoster.xfilesharing_download(resp, 1)[0]()
    check_errors(chunk, resp)

    m = re.search('You have to wait (.*?) till next download', resp.text)
    if m:
        wait = hoster.parse_seconds2(m.group(1)) + time.time()
        if wait > 300:
            chunk.ip_blocked(wait)

    submit, data = hoster.xfilesharing_download(resp, 2)

    wait = resp.soup.find('span', id='uglrto')
    if wait:
        wait = int(wait.text.strip().rplit(' ', 1)[1]) + time.time()

    for result, challenge in chunk.solve_captcha('recaptcha', parse=resp.text, retries=5):
        data['recaptcha_challenge_field'] = challenge
        data['recaptcha_response_field'] = result
        if wait and wait - time.time() > 0:
            chunk.wait(wait - time.time())
        resp = submit(allow_redirects=False)
        if resp.status_code == 302:
            return resp.headers['Location']
        check_errors(chunk, resp)
