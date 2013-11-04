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

from ... import hoster, javascript

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'dfiles.eu'
    alias = ['depositfiles.com']
    favicon_url = 'http://static344.dfiles.eu/images/favicon.ico'
    patterns = [
        hoster.Matcher('https?', ['*.dfiles.eu', '*.depositfiles.com'], '/(\w{1,3}/)?files/(?P<id>[\w\d]+)')
    ]
    url_template = 'http://dfiles.eu/files/{id}'

def check_errors(ctx, text):
    if 'You have reached your download time limit.' in text:
        ctx.no_more_free_traffic(600)
    elif 'This file does not exist,' in text:
        ctx.set_offline()
    m = re.search(r'Attention! Connection limit has been exhausted for your IP address! Please try in\s+(\d+) (second|minute|hour|day)', text)
    if m:
        seconds = int(m.group(1)) * {'second': 1, 'minute': 60, 'hour': 3600, 'day': 3600*24}[m.group(2)]
        ctx.ip_blocked(seconds=seconds, need_reconnect=True)

def on_check_http(file, resp):
    check_errors(file, resp.text)
    try:
        name = resp.soup.select('div.file_name b')[0].get('title').strip()
    except IndexError:
        script = resp.soup.select('div.info script')[0].text
        name = hoster.Soup(javascript.execute('document={};document.write=function(x){document.y=x};'+script+'document.y')).find('b').text.strip()
    size = resp.soup.select('div.file_size b')[0].text.strip()
    file.set_infos(name, size)

def on_download_premium(chunk):
    return chunk.url

def on_download_free(chunk):
    resp = chunk.account.get(chunk.url)
    check_errors(chunk, resp.text)
    
    resp = chunk.account.post('http://depositfiles.com/en/files/'+chunk.pmatch.id, data=dict(gateway_result=1))
    check_errors(chunk, resp.text)

    fid = re.search(r"var fid = '([\w\d]+)';", resp.text).group(1)
    wait = re.search(r"setTimeout\('show_url\((\d+)\)'", resp.text).group(1)
    if wait:
        wait = time.time() + int(wait)

    challenge_id = '6LdRTL8SAAAAAE9UOdWZ4d0Ky-aeA7XfSqyWDM2m' # stolen from http://static303.dfiles.eu/js/base2.js
    for result, challenge in chunk.solve_captcha('recaptcha', challenge_id=challenge_id, retries=5):
        if wait and wait > time.time():
            chunk.wait(wait - time.time())
        params = dict(fid=fid, challenge=challenge, response=result)
        r = chunk.account.get("http://depositfiles.com/en/get_file.php", params=params, referer=resp.url)
        m = re.search(r'<form id="downloader_file_form" action="(.*?)"', r.text)
        if m:
            return m.group(1)
        if '<form action="" onsubmit="check_recaptcha(' in r.text:
            continue
        check_errors(chunk, r.text)
        print r.text

    
extra_persistent_account_columns = ['token', 'member_passkey']

def on_initialize_account(self):
    self.set_user_agent()
    self.get("http://dfiles.eu/switch_lang.php?lang=en", allow_redirects=False)

    if not self.username:
        return

    if self.token:
        self.browser.cookies['autologin'] = self.token
        resp = self.get('http://dfiles.eu/gold/payment_history.php')
        if '<li><a href="/gold/profile.php" >Personal info</a></li>' in resp.text:
            check_account(self, resp)
            return
        self.token = None
        self.member_passkey = None

    def test_captcha(result, challenge):
        data = dict(
            login=self.username,
            password=self.password,
            recaptcha_challenge_field=challenge,
            recaptcha_response_field=result)
        resp = self.post("http://dfiles.eu/api/user/login", referer="http://dfiles.eu/login.php", data=data)
        json = resp.json()
        if json.get('error') != 'CaptchaInvalid':
            return json

    #challenge_id = '6LdRTL8SAAAAAE9UOdWZ4d0Ky-aeA7XfSqyWDM2m' # stolen from http://static303.dfiles.eu/js/base2.js
    #json = self.solve_captcha('recaptcha', browser=self, challenge_id=challenge_id, testfunc=test_captcha, retries=5)
    json = test_captcha(None, None)

    error = json.get('error')
    if error == 'LoginInvalid':
        self.login_failed()
    elif error:
        self.plugin_out_of_date(msg='unknown error: {}'.format(error))
    elif json.get('status') != 'OK':
        self.plugin_out_of_date(msg='unknown status: {}'.format(json.get('status')))
    elif 'data' not in json:
        self.plugin_out_of_date(msg='missing data')

    json = json['data']
    if 'token' not in json:
        self.plugin_out_of_date(msg='missing auth token')
    elif 'member_passkey' not in json:
        self.plugin_out_of_date(msg='missing member_passkey')

    self.token = json['token']
    self.member_passkey = json['member_passkey']

    if json['mode'] == 'free':
        self.premium = False
        return True

    # TODO: premium account options (expire, traffic ...)
    resp = self.get('http://dfiles.eu/gold/payment_history.php')
    check_account(self, resp)

def check_account(self, resp):
    #TODO foo bar
    #self.premium = j['premium']
    #self.traffic = j['traffic_left']
    #self.expires = j['expire_time']
    pass
