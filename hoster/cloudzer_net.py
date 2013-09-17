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
import requests

from ... import hoster, javascript
from ...account import verify

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'cloudzer.net'
    patterns = [
        hoster.Matcher('https?', '*.clz.to', '!/<id>'),
        hoster.Matcher('https?', '*.cloudzer.net', '!/file/<id>'),
        hoster.Matcher('https?', '*.cloudzer.net', id='id')
    ]
    url_template = 'http://cloudzer.net/file/{id}'

    max_filesize_free = hoster.GB(1)
    max_filesize_premium = hoster.GB(2)

    #max_chunks_premium = 1
    
    has_captcha_free = True
    max_download_speed_free = 50
    waiting_time_free = 1

def check_maintenance(context, data):
    if 'maintenance' in data or 'Wartungsarbeiten' in data:
        context.retry('hoster is in maintenance mode', 30)

def on_check(file):
    id = file.pmatch.id
    try:
        resp = file.account.get("http://cloudzer.net/file/{id}/status".format(id=id), allow_redirects=False)
        if resp.status_code == 302: # redirect to http://cloudzer.net/404
            file.set_offline()
        lines = resp.text.splitlines()
        if len(lines) != 2:
            check_maintenance(file, resp.text)
            file.retry('unknown check error', 60)
        file.set_infos(name=lines[0], approx_size=lines[1])
    except requests.HTTPError as e:
        if str(e) == "HTTP Error 404: Not Found":
            file.set_offline()
        raise

def on_download_premium(chunk, ignore_init_resume=False):
    resp = chunk.account.get(chunk.file.url, stream=True, chunk=None if ignore_init_resume else chunk)
    if not 'Content-Disposition' in resp.headers:
        if resp.status_code == 416 and ignore_init_resume is False:
            return on_download_premium(chunk, True)
        check_maintenance(chunk, resp.text)
        f = re.search(r'<div class="tfree".*\s*<form method="post" action="(.*?)"', resp.content)
        if not f:
            # TODO: check for "technical problems" error
            chunk.no_download_link(60)
        resp = chunk.account.get(f.group(1), stream=True, chunk=chunk)
    elif ignore_init_resume is True:
        chunk.plugin_out_of_date(msg='resume ignored but got content range', retry=60)
    if not resp.ok:
        print resp.text
    return resp

def on_download_free(chunk):
    if verify:
        agent = verify.get_agent("cloudzer.net")
        print "setting agent", agent
        chunk.account.set_user_agent(user_agent=agent)
    
    resp = chunk.account.get(chunk.file.url, allow_redirects=False)
    if resp.status_code == 302:
        return resp.headers["Location"]
    resp.raise_for_status()
    
    refid = re.search(r'ref_user=(.*?)\&', resp.text)
    if refid:
        chunk.account.set_buy_url("http://cloudzer.net/ref/"+refid.group(1))
    
    if 'var free_enabled = false;' in resp.text:
        chunk.account.no_free_traffic(300, need_reconnect=True)

    found = re.search(r"Wartezeit: (\d+) Sekunden", resp.text)
    if not found:
        chunk.premium_needed()

    chunk.wait(int(found.group(1)))

    js = chunk.account.get('http://cloudzer.net/js/download.js')

    url = "http://cloudzer.net/io/ticket/captcha/%s" % chunk.file.pmatch.id

    for result, challenge in chunk.solve_captcha('recaptcha', parse=js.text, retries=5):
        data = {"recaptcha_challenge_field": challenge, "recaptcha_response_field": result}
        resp = chunk.account.post(url, data=data)
        data = javascript.loads(resp.text)
        """if u"limit-size" in resp.text:
            chunk.premium_needed()
        elif u"limit-slot" in resp.text: #temporary restriction so just wait a bit
            chunk.account.no_free_traffic(300, need_reconnect=True)
        elif u"limit-parallel" in resp.text:
            chunk.account.ip_blocked(300, need_reconnect=True)"""
        if u'err' in data:
            if data['err'] == u'captcha':
                chunk.log.info('invalid captcha')
            elif 'This file exceeds the max. filesize which can be downloaded' in data['err']:
                chunk.no_more_free_traffic()
            elif data['err'] == u'limit-dl' or data['err'].startswith(u"You have reached the max. number of possible free downloads for this hour"):
                chunk.account.no_free_traffic(3600, need_reconnect=True)
            else:
                chunk.plugin_out_of_date(msg='unknown captcha error: {}'.format(data['err']), seconds=1800)
        elif u'type' in data and data['type'] == u'download':
            return data['url']
        else:
            chunk.plugin_out_of_date(msg='error parsing captcha result')


def on_initialize_account(self):
    self.get("http://cloudzer.net/language/en")

    if not self.username:
        return

    resp = self.post("http://cloudzer.net/io/login", data={"id": self.username, "pw": self.password})
    if resp.status_code != 200 or not "auth" in self.cookies:
        check_maintenance(self, resp.content)
        self.login_failed()

    resp = self.get('http://cloudzer.net/me')
    check_maintenance(self, resp.content)

    self.premium = '<div class="status status_premium">Premium</div>' in resp.text
    if not self.premium:
        return

    self.traffic = re.search(r'<div class="head">Downloadtraffic</div>\s*<div class="clearfix"></div>\s*<div class="body">(.*?)</div>', resp.text, re.MULTILINE).group(1)

    expires = re.search(r'<div class="status status_premium">Premium</div></a><br/>\s*([^<]+)', resp.text, re.MULTILINE).group(1).strip()
    if expires == "unlimited":
        self.expires = None
    else:

        expires = re.findall(r"(\d+) (weeks|days|hours)", expires)
        e = time.time()
        for n, u in expires:
            e += 3600 * int(n) * {"weeks": 168, "days": 24, "hours": 1}[u]
        self.expires = e
