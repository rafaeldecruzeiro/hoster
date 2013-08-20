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

from ... import hoster, core

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'bitshare.com'
    favicon_url = 'http://bitshare.com/static/images/favicon.ico'
    patterns = [
        hoster.Matcher('https?', '*.bitshare.com', '!/files/<id>').set_tag('f'),
        hoster.Matcher('https?', '*.bitshare.com', f='id').set_tag('f'),
        hoster.Matcher('https?', '*.bitshare.com', d='id').set_tag('d')
    ]
    url_template = 'http://www.bitshare.com/?{tag}={id}'

def on_check(file):
    if file.pmatch.tag == 'd': # folder
        """ generated source for method decryptIt """
        links = list()
        resp = file.account.get(file.url)
        if "Folder can not be found!" in resp.content:
            file.set_offline()
        if "Folder does not contain any files" in resp.content:
            file.delete_after_greenlet()
            return
        fpName = re.search("<h1>View public folder \"(.*?)\"</h1>", resp.text).group(1)
        links = re.findall("<td><a href=\"(http://.*?)\"", resp.text).groups(1)
        if links is None or len(links) == 0:
            links = re.findall("\"(http://bitshare\.com/files/[a-z0-9]+/.*?)\"", resp.text).group(1)
        if links is None or len(links) == 0:
            file.delete_after_greenlet()
            return
        for link in links:
            links.append(link.group(1))
        core.add_links(links, package_name=fpName)
        file.delete_after_greenlet()
    else:
        data = {
            "action": "getFileStatus",
            "files": file.url,
        }
        resp = file.account.post("http://bitshare.com/api/openapi/general.php", data=data)
        f = resp.content.splitlines()[0]
        link, status, has, name, filesize = f.split("#")
        if status != "online":
            file.fatal(status)
        else:
            file.set_infos(name=name, size=filesize)

def parse_infos(file, text):
    m = re.search(r'''(>We are sorry, but the requested file was not found in our database|>Error - File not available<|The file was deleted either by the uploader, inactivity or due to copyright claim)''', text)
    if m:
        file.set_offline()

    m = re.search(r'<h1>(Downloading|Streaming)\s(?P<name>.+?)\s-\s(?P<size>[\d.]+)\s(?P<units>..)yte</h1>', text)
    name = m.group('name')
    size = int(float(m.group('size'))*1024**{'KB': 1, 'MB': 2, 'GB': 3}[m.group('units')])

    return name, size

def on_download_premium(chunk):
    resp = chunk.account.get(chunk.file.url, allow_redirects=False, stream=True)
    if resp.headers.get('Location', None) and re.search(r'://s\d+\.bitshare\.com/download\.php', resp.headers['Location']):
        resp.close()
        return resp.headers['Location']
    raise NotImplementedError('direct download')

def on_download_free(chunk):
    resp = chunk.account.get(chunk.url)
    parse_infos(chunk.file, resp.text)
    check_errors(chunk, resp.text)

    v = resp.cookies["PHPSESSID"]
    del chunk.account.cookies["PHPSESSID"] # 'set-cookie': 'PHPSESSID=1jlb09b9gkg6oaoj8ih9h8k7s2; path=/', 'expires': 'Thu, 19 Nov 1981 08:52:00 GMT' srsly?
    chunk.account.cookies["PHPSESSID"] = v

    ajax_id = re.search(r'var ajaxdl = "(.*?)";', resp.text).group(1)

    data = {"request": "generateID", "ajaxid": ajax_id}
    r = chunk.account.post("http://bitshare.com/files-ajax/{}/request.html".format(chunk.pmatch.id), data=data)
    check_errors(chunk, r.text)
    check_ajax_errors(chunk, r.text)

    parts = r.text.split(":")
    #filetype = parts[0]
    wait = int(parts[1])
    captcha = int(parts[2])

    if wait > 0:
        chunk.wait(wait)

    if captcha:
        for result, challenge in chunk.solve_captcha('recaptcha', parse=resp.text):
            data = {"request": "validateCaptcha", "ajaxid": ajax_id, "recaptcha_challenge_field": challenge, "recaptcha_response_field": result}
            r = chunk.account.post("http://bitshare.com/files-ajax/{}/request.html".format(chunk.pmatch.id), data=data)
            if "SUCCESS" in r.text:
                break
            check_errors(chunk, r.text)
            check_ajax_errors(chunk, r.text)

    data = {"request": "getDownloadURL", "ajaxid": ajax_id}
    r = chunk.account.post("http://bitshare.com/files-ajax/{}/request.html".format(chunk.pmatch.id), data=data)
    check_errors(chunk, r.text)
    check_ajax_errors(chunk, r.text)
    download_url = r.text.split("#")[-1]

    resp = chunk.account.get(download_url.replace('%0D%0A', ''), stream=True)

    return resp

def check_errors(chunk, text):
    if "Your Traffic is used up for today" in text:
        chunk.account.no_free_traffic(3600, need_reconnect=True)
    if "Only Premium members can access this file" in text:
        chunk.premium_needed()
    if "Sorry, you cant download more then 1 files at time" in text:
        chunk.account.ip_blocked(300)
    if "You reached your hourly traffic limit" in text:
        m = re.search(r'id="blocktimecounter">(\d+) Seconds</span>', text)
        if m is None:
            m = re.search(r'var blocktime = (\d+);', text)
        if m:
            wait = m.group(1)
        else:
            wait = 600
        chunk.wait(wait)

def check_ajax_errors(chunk, text):
    if "ERROR:Session timed out" in text:
        chunk.account.reboot()
        chunk.retry('session timed out', 1)
    if "ERROR" in text:
        chunk.plugin_out_of_date(msg=text.split(':')[-1].strip())

def on_initialize_account(self):
    self.sid = None
    #self.set_user_agent()
    self.cookies['language_selection'] = 'EN'
    
    if self.username is None:
        return False

    resp = self.post("http://bitshare.com/login.html", data={"user": self.username, "password": self.password, "submit": "Login", "rememberlogin": "on"})
    if "Wrong Username or Password!" in resp.text:
        self.login_failed()

    resp = self.get("http://bitshare.com/myaccount.html", allow_redirects=False)
    if resp.status_code == 302:
        self.premium = False
        return

    if '"http://bitshare.com/myupgrade.html">Free' in resp.text:
        self.premium = False
        return

    m = re.search(r"Valid until:\s*(.*?)\s*</div>", resp.text, re.MULTILINE)
    if m:
        self.expires = m.group(1)
        self.premium = self.expires > time.time() and True or False
    else:
        self.premium = False
