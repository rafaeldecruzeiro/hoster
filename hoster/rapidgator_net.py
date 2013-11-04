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
    name = 'rapidgator.net'
    patterns = [
        hoster.Matcher('https?', '*.rapidgator.net', '!/file/<id>/<name>.html'),
        hoster.Matcher('https?', '*.rapidgator.net', '!/file/<id>'),
    ]
    url_template = 'http://rapidgator.net/file/{id}'

    max_filesize_free = hoster.MB(500)
    max_filesize_premium = hoster.GB(2)

extra_persistent_account_columns = ['sid']


def on_check(file):
    resp = file.account.get(file.url)
    name, size = get_file_infos(file, resp.text)
    file.set_infos(name=name, approx_size=size)


def get_file_infos(file, text):
    if "File not found" in text or 'Error 404' in text:
        file.set_offline()
    if "You can download files up to 500 MB in free mode" in text or "This file can be downloaded by premium only" in text:
        file.premium_needed()

    m = re.search(r"Downloading:\s+</strong>([^<>\"]+)</p>", text)
    if not m:
        m = re.search(r"<title>Download file ([^<>\"]+)</title>", text)
    if not m:
        file.parse_error('filename')
    name = m.group(1)

    m = re.search(r"File size:\s+<strong>([^<>\"]+)</strong>", text)
    if not m:
        file.parse_error('filesize')
    size = m.group(1)

    return name, size


def call_api(chunk, cmd):
    params = {'sid': chunk.account.sid, 'url': chunk.file.url}
    resp = chunk.account.get('http://rapidgator.net/api/file/{}'.format(cmd), params=params)
    json = resp.json()
    status = json['response_status']
    msg = json['response_details']

    if status == 200:
        return json['response']
    elif status == 423:
        chunk.account.reboot()
        chunk.retry(msg, 1)
    else:
        chunk.account.reboot()
        chunk.retry(msg, 60)


def on_download_premium(chunk):
    data = call_api(chunk, 'info')
    chunk.file.set_infos(name=data['filename'], size=int(data['size']), hash_type='md5', hash_value=data['hash'])
    return call_api(chunk, 'download')['url']


def on_download_free(chunk):
    resp = chunk.account.get(chunk.file.url)
    get_file_infos(chunk.file, resp.text)

    if "You can download files up to 500 MB in free mode" in resp.text or "This file can be downloaded by premium only" in resp.text:
        chunk.premium_needed()

    check_wait(chunk.file, resp.text)

    js = dict(re.findall(r"\s+var\s*(startTimerUrl|getDownloadUrl|captchaUrl|fid|secs)\s*=\s*'?(.*?)'?;", resp.text))

    headers = dict()
    headers['X-Requested-With'] = 'XMLHttpRequest'
    headers['Referer'] = chunk.file.url

    url = "http://rapidgator.net{}".format(js.get('startTimerUrl', '/download/AjaxStartTimer'))
    resp = resp.get(url, headers=headers, params={'fid': js["fid"]})
    js.update(resp.json())

    chunk.file.wait(int(js.get('secs', 30)) + 1)

    url = "http://rapidgator.net{}".format(js.get('getDownloadUrl', '/download/AjaxGetDownload'))
    resp = resp.get(url, headers=headers, params={'sid': js["sid"]})
    js.update(resp.json())

    del headers['X-Requested-With']

    url = "http://rapidgator.net%s" % js.get('captchaUrl', '/download/captcha')
    resp = resp.get(url, headers=headers)

    m = re.search(r'http://api\.adscaptcha\.com/Get\.aspx\?([^"\']*)', resp.text)
    if m:
        challenge_id = m.group(1)
        captcha = 'adscaptcha'
    else:
        m = re.search(r'"http://api\.recaptcha\.net/challenge?k=(.*?)"', resp.text)
        if m:
            challenge_id = m.group(1)
            captcha = 'recaptcha'
        else:
            m = re.search(r'http:\/\/api\.solvemedia\.com\/papi\/challenge\.script\?k=(.*?)"', resp.text)
            if m:
                challenge_id = m.group(1)
                captcha = 'solvemedia'
            else:
                chunk.parse_error('captcha')
    
    check_wait(chunk.file, resp.text)
    for result, challenge in chunk.solve_captcha(captcha, challenge_id=challenge_id, retries=5):
        data = {"DownloadCaptchaForm[captcha]": "", "adcopy_challenge": challenge, "adcopy_response": result}
        resp = resp.post(url, headers=headers, data=data)
        if 'The verification code is incorrect' not in resp:
            break
        check_wait(chunk.file, resp.text)

    m = re.search(r"location\.href = '(.*?rapidgator\.net.*?download.*?)'", resp.text)
    if not m:
        m = re.search(r"return '(.*?rapidgator\.net.*?download.*?)'", resp.text)
    if not m:
        print resp.text
        chunk.no_download_link()

    return m.group(1)


def check_wait(file, text):
    wait = re.search(r"(?:Delay between downloads must be not less than|Try again in)\s*(\d+)\s*(hour|min)", text)
    if wait:
        t = int(wait.group(1)) * {"hour": 3600, "min": 60}[wait.group(2)]
        if t > 3600:
            file.ip_blocked(t)
        else:
            file.wait(t)
        return

    wait = re.search(r"You have reached your (daily|hourly) downloads limit", text)
    if wait:
        file.ip_blocked(3600)


def on_initialize_account(account):
    account.sid = None

    if account.username is None:
        return False

    data = {"username": account.username, "password": account.password}
    resp = account.post("http://rapidgator.net/api/user/login", data=data)
    if resp.status_code != 200:
        account.fatal(resp.json()['response_details'])

    account.sid = str(resp.json()['response']['session_id'])

    data = {"sid": account.sid}
    resp = account.get("http://rapidgator.net/api/user/info", params=data)
    j = resp.json()
    if resp.status_code != 200:
        account.fatal(j['response_details'])

    account.expires = j['response']['expire_date']
    account.traffic = j['response']['traffic_left']
    if account.traffic > 0 and account.expires > time.time():
        account.premium = True
    else:
        account.premium = False
