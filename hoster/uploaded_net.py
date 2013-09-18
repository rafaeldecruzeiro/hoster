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

from ... import javascript
from ...hoster import host, HttpPremiumHoster, Matcher, sizetools, serialize_html_form
from ...core import add_links
from ...account import verify

@host
class this:
    model = HttpPremiumHoster
    name = 'uploaded.net'
    patterns = [
        Matcher('https?', '*.ul.to', '!/<id>').set_tag("file"),
        Matcher('https?', ['*.uploaded.to', '*.uploaded.net'], '!/file/<id>').set_tag("file"),
        Matcher('https?', ['*.uploaded.to', '*.uploaded.net'], id='id').set_tag("file"),
        Matcher('https?', ['*.uploaded.net'], '!/folder/<id>').set_tag("folder"),
    ]
    url_template = 'http://uploaded.net/{tag}/{id}'

    max_filesize_free = sizetools.GB(1)
    max_filesize_premium = sizetools.GB(2)

    #max_chunks_premium = 1

    has_captcha_free = True
    max_download_speed_free = 100
    waiting_time_free = 1

def on_check(file):
    if file.pmatch.tag == "folder":
        resp = file.account.get(file.url, allow_redirects=False)
        if not resp.ok or resp.status_code == 302:
            file.set_offline()
        links = ["http://uploaded.net/file/"+i for i in re.findall(r"\<a\ href=\"file\/(.*?)/from/", resp.text)]
        if links:
            add_links(links)
        file.delete_after_greenlet()
        return
        
    if file.account.username and file.account.enabled:
        data = file.account.get("http://uploaded.net/api/download/Info", params=dict(auth=file.pmatch.id))
        if data.ok:
            data = data.json()
            if not "err" in data:
                file.set_infos(name=data["info"]["name"], size=data["info"]["size"])
            else:
                file.set_offline()
            return
    resp = file.account.get("http://uploaded.net/file/{id}/status".format(id=file.pmatch.id), allow_redirects=False)
    if resp.status_code == 302 or not resp.ok: # redirect to http://uploaded.net/404
        file.set_offline()
    check_maintenance(file, resp.content)
    lines = resp.text.splitlines()
    if len(lines) != 2:
        check_maintenance(file, resp.text)
        file.retry('unknown check error', 60)
    file.set_infos(name=lines[0], approx_size=lines[1].replace(".", "").replace(",", "."))

def on_download_premium(chunk, ignore_init_resume=False):
    resp = chunk.account.get(chunk.file.url, stream=True, chunk=None if ignore_init_resume else chunk)
    if not 'Content-Disposition' in resp.headers:
        if resp.status_code == 416 and ignore_init_resume is False:
            return on_download_premium(chunk, True)
        check_maintenance(chunk, resp.text)
        f = re.search(r'<div class="tfree".*\s*<form method="post" action="(.*?)"', resp.content)
        if not f:
            # TODO: check for "technical problems" error
            if 'Page not found' in resp.text:
                chunk.file.set_offline()
            chunk.no_download_link(60)
        resp = chunk.account.get(f.group(1), stream=True, chunk=chunk)
    elif ignore_init_resume is True:
        chunk.plugin_out_of_date(msg='resume ignored but got content range', retry=60)
    if not resp.ok:
        print resp.text
    return resp

def on_download_free(chunk):
    if verify:
        agent = verify.get_agent("uploaded.net")
        print "setting agent", agent
        chunk.account.set_user_agent(user_agent=agent)
    resp = chunk.account.get(chunk.file.url, allow_redirects=False)
    if resp.status_code == 302:
        return resp.headers["Location"]
    resp.raise_for_status()
    refid = re.search(r'ref_user=(.*?)\&', resp.text)
    if refid:
        chunk.account.set_buy_url("http://ul.to/ref/"+refid.group(1))
    check_maintenance(chunk, resp.text)
    if 'var free_enabled = false;' in resp.text:
        chunk.account.no_more_free_traffic(300, need_reconnect=True)

    form = resp.soup.find('h2', text=lambda a: 'Authentification' in a)
    if form:
        form = form.find_parent('form')
        action, data = serialize_html_form(form)
        data['pw'] = chunk.solve_password_www(retries=1).next()
        resp = resp.post(action, data=data)
        if resp.soup.find('h2', text=lambda a: 'Authentification' in a):
            chunk.password_invalid()

    m = re.search(r"Current waiting period: <span>(\d+)</span> seconds", resp.text)
    if not m:
        chunk.premium_needed()

    chunk.wait(int(m.group(1)))

    js = chunk.account.get('http://uploaded.net/js/download.js')

    url = "http://uploaded.net/io/ticket/captcha/%s" % chunk.file.pmatch.id

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
            elif data['err'] == u'limit-dl' or data['err'].startswith(u"You have reached the max. number of possible free downloads for this hour"):
                chunk.account.no_free_traffic(3*3600, need_reconnect=True)
            else:
                chunk.plugin_out_of_date(msg='unknown captcha error', seconds=1800)
        elif u'type' in data and data['type'] == u'download':
            return data['url']
        else:
            chunk.plugin_out_of_date(msg='error parsing captcha result')

def check_maintenance(context, data):
    if 'maintenance' in data or 'Wartungsarbeiten' in data:
        context.retry('hoster is in maintenance mode', 30)

def on_initialize_account(account):
    account.get("http://uploaded.net/language/en")
    if not account.username:
        return

    resp = account.post("http://uploaded.net/io/login", data={"id": account.username, "pw": account.password})
    if resp.status_code != 200 or not "auth" in account.cookies:
        check_maintenance(account, resp.content)
        account.login_failed()
    account.get("http://uploaded.net/language/en")

    resp = account.get('http://uploaded.net/me')
    check_maintenance(account, resp.content)
    th = resp.soup("th")
    if th and th[1].text == u"Premium":
        account.premium = True
    else:
        account.premium = False
        return
    account.traffic = resp.soup.find("b", class_="cB").text
    th = resp.soup("th")
    expires = th[3].text
    if expires == "unlimited":
        account.expires = None
    else:
        expires = re.findall(r"(\d+) (weeks|days|hours)", expires)
        e = time.time()
        for n, u in expires:
            e += 3600 * int(n) * {"weeks": 168, "days": 24, "hours": 1}[u]
        account.expires = e
