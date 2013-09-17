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

import os
import re
import urllib
from ... import hoster

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'nowvideo.eu'
    patterns = [
        hoster.Matcher('https?', '~(.*\.)?nowvideo.(eu|ch|at|co)', '/video/(?P<id>.*)'),
        hoster.Matcher('https?', '~(.*\.)?nowvideo.(eu|ch|at|co)', '!/embed.php', v="id"),
        hoster.Matcher('https?', '~(.*\.)?nowvideo.(eu|ch|at|co)', '!/mobile', id="id")
    ]
    url_template = 'http://www.nowvideo.eu/video/{id}'
    can_resume_free = True

def on_initialize_account(account):
    account.set_user_agent(os='ipad')
    if account.username is None:
        return
    data = {
        "register": "Login",
        "user": account.username,
        "pass": account.password}
    resp = account.post("http://www."+this.name+"/login.php", params={"return": ""}, data=data, allow_redirects=False)
    if 'user' not in resp.cookies and 'pass' not in resp.cookies:
        account.login_failed()
    # TODO: check for premium status
    account.premium = False

def get_infos(file, resp):
    """deprecated, non-mobile user agent. maybe useful for premium accounts"""
    h3 = resp.soup.find('h3')
    if h3 and 'The file is being converted' in h3.text:
        file.temporary_unavailable(msg='file convert in progress', seconds=300)
    try:
        name = resp.soup.find_all(class_='video_details')[1].find('h4').text
    except IndexError:
        raise
    name = os.path.splitext(name)[0]+'.flv'

    filekey = re.search('flashvars\.filekey="(.*?)"', resp.text).group(1)
    filekey = urllib.quote_plus(filekey)
    #filekey = filekey.replace('.', '%2E').replace('-', '%2D')
    params = {
        'pass': 'undefined',
        'user': 'undefined',
        'cid': '1',
        'cid2': 'undefined',
        'cid3': 'undefined',
        'file': file.pmatch.id,
        'key': filekey}
    resp = file.account.get('http://www.'+this.name+'/api/player.api.php', params=params)
    url = re.search("url=(http://[^<>\"]*?\\.flv)\\&title", resp.text).group(1)
    return url, name

def check_errors(ctx, resp):
    if 'This file no longer exists on our servers' in resp.text:
        ctx.set_offline()

def on_check_http(file, resp):
    if file.extra is None:
        links = list()
        check_errors(file, resp)
        name = resp.soup.find('h3').text
        name = os.path.splitext(name)[0]
        try:
            sources = [(s.get('src'), s.get('type')) for s in resp.soup.select('video source')]
        except AttributeError:
            sources = None
        if not sources:
            sources = [(resp.soup.select('h3 a')[0].get('href'), 'a')]
        for src, type in sources:
            url = hoster.add_extra(file.url, type)
            path = hoster.Url(src).path
            ext = os.path.splitext(path)[1] or '.flv'
            links.append(dict(url=url, name=name+ext))
        return links
    if file.extra == 'a':
        url = resp.soup.select('h3 a')[0].get('href')
    else:
        url = resp.soup.find('source', type=file.extra).get('src')
    hoster.check_download_url(file, url)

def on_download_free(chunk):
    resp = chunk.account.get(chunk.url, use_cache=True)
    check_errors(chunk, resp)
    if chunk.extra == 'a':
        return resp.soup.select('h3 a')[0].get('href')
    else:
        return resp.soup.find('source', type=chunk.extra).get('src')
