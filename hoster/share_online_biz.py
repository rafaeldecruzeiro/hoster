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
import dateutil.parser

from ... import hoster

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'share-online.biz'
    patterns = [
        hoster.Matcher('https?', ['*.share-online.biz', '*.egoshare.com'], '!/download.php', id='id'),
        hoster.Matcher('https?', ['*.share-online.biz', '*.egoshare.com'], '!/dl/<id>'),
    ]
    url_template = 'http://www.share-online.biz/dl/{id}'
    
    max_filesize_free = hoster.GB(1)
    max_filesize_premium = hoster.GB(2)
    max_chunks_premium = 3

    has_captcha_free = True
    max_download_speed_free = 50
    waiting_time_free = 1

def on_check(file):
    id = file.pmatch.id
    try:
        try:
            resp = file.account.get("https://api.share-online.biz/linkcheck.php", params={"md5": 1, "links": id})
        except requests.ConnectionError:
            file.retry('connection error', 5)
        fields = resp.content.splitlines()[0].split(';')
        if fields[1] != 'OK':
            file.set_offline(fields[1])
        file.set_infos(name=fields[2], size=int(fields[3]), hash_type='md5', hash_value=fields[4].strip().lower())
    except requests.HTTPError:
        raise

def account_request(ctx, act="userDetails", lid=False):
    payload = {
        "username": ctx.account.username,
        "password": ctx.account.password,
        "act": act,
    }
    if lid:
        payload["act"] = "download"
        payload["lid"] = ctx.pmatch.id
        
    resp = ctx.account.get("https://api.share-online.biz/account.php", params=payload)
    
    try:
        #print repr(resp.content)
        data = dict(re.split(r"=|:\ ?", i, 1) for i in resp.content.splitlines() if i.strip())
    except ValueError:
        ctx.fatal(resp.content)
    print data
    return data
    
def start_download(chunk, url, f=True):
    resp = chunk.account.get(url, stream=True, chunk=chunk, allow_redirects=False)
    if "Location" in resp.headers:
        error = resp.headers["Location"].rsplit("/", 1)[-1]
        if error == "ip":
            chunk.ip_blocked(180, need_reconnect=f)
        else:
            chunk.file.fatal("Error:", error)
    else:
        return resp
        
def on_download_premium(chunk):
    data = account_request(chunk)
    try:
        chunk.account.cookies["a"] = data["a"]
    except KeyError:
        chunk.premium_needed()
    try:
        chunk.account.cookies["dl"] = data["dl"]
    except KeyError:
        pass
        
    try:
        data = account_request(chunk, lid=True)
    except ValueError:
        chunk.fatal(data)
    else:
        if data["STATUS"] != "online":
            chunk.retry("file not online: {}".format(data["STATUS"]), 180)
        if not data["URL"].startswith("http"):
            chunk.retry("no download: {}".format(data["URL"]), 180)
        resp = chunk.account.get(data["URL"], chunk=chunk, stream=True)
        if not 'Content-Disposition' in resp.headers:
            resp.close()
            if '/failure/ip</title>' in resp.text:
                chunk.ip_blocked(seconds=180)
            else:
                chunk.no_download_link(seconds=180)
        return resp

def on_download_free(chunk):
    resp = chunk.account.get(chunk.file.url)
    chunk.wait(3)
    resp = chunk.account.post("{}/free/".format(chunk.file.url), data={"dl_free": 1, "choice": "free"})
    found = re.search(r"/failure/(.*?)/1", resp.url)
    if found:
        err = found.group(1)
        found = re.search(r'<p class="b">Information:</p>\s*<div>\s*<strong>(.*?)</strong>', resp.text)
        msg = found.group(1) if found else ""
        this.log.error(err, msg or "Unknown error occurred")
                    
        if err in ('freelimit', 'size', 'proxy'):
            chunk.file.fatal(msg or "Premium account needed")
        if err in ('invalid'):                      
            chunk.file.fatal(msg or "File not available")
        elif err in ('server'):
            chunk.file.retry('server', 600)
        elif err in ('expired'):
            chunk.file.retry('expired', 30)
        else:
            chunk.file.retry(300, True)

    m = re.search(r'var wait=(\d+);', resp.content)
    wait = m and int(m.group(1)) or 30
    t = time.time()
    for result, challenge in chunk.solve_captcha('recaptcha', challenge_id='6LdatrsSAAAAAHZrB70txiV5p-8Iv8BtVxlTtjKX', retries=5):
        data = {"dl_free": 1, 
            "recaptcha_challenge_field": challenge, 
            "recaptcha_response_field": result}
        if time.time() - t < wait:
            chunk.wait(wait - (time.time() - t))
        resp = chunk.account.post("{}/free/captcha/{}".format(chunk.file.url, int(time.time()*1000)), data=data)
        if resp.content.strip() != '0':
            break
    
    url = resp.content.strip().decode('base64')
    if not url.startswith('http://'):
        #TODO: change this error message, send script error to backend
        chunk.no_download_link()
    chunk.wait(31)
    return start_download(chunk, url, True)
    

def on_initialize_account(account):
    account.set_user_agent()
    account.cookies["page_language"] = "english"
    if account.username is None:
        return
    
    payload = {
        "user": account.username,
        "pass": account.password,
    }
    resp = account.post("https://www.share-online.biz/user/login", data=payload)
    if resp.soup.find("div", id="login_error"):
        account.premium = False
        account.login_failed()
        return
    details = resp.soup.find("div", id="account_details")
    try:
        for n in details.find_all("p", **{"class": "p_l"}):
            if n.text.strip().startswith("Your Account-Type"):
                v = n.find_next_sibling()
                if v.text.strip().lower() in {u"premium", u"vip"}:
                    account.premium = True
                else:
                    account.premium = False
                    return
            elif n.text.strip().startswith("Account valid until"):
                v = n.find_next_sibling()
                account.expires = time.mktime(dateutil.parser.parse(v.text.strip(), dayfirst=True).timetuple())
            elif n.text.strip().startswith("Bandwidth"):
                v = n.find_next_sibling()
                account.traffic = 110*float(v.find("img")["title"].split(u"%")[0])/100*1024*1024*1024 # they use 110gb daily limit, show daily
    except AttributeError:
        print details
        raise
    print account.serialize()
