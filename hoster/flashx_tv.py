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
from ... import hoster

@hoster.host
class this:
    model = hoster.HttpHoster
    name = 'flashx.tv'
    patterns = [
        hoster.Matcher('https?', '*.flashx.tv', '!/video/<id>/')
    ]
    url_template = 'http://flashx.tv/video/{id}/'
    can_resume = True
    max_chunks = 2

def check_errors(ctx, resp):
    error = resp.soup.find('div', 'cb_error')
    if not error:
        error = resp.soup.find('font', color='red')
    if error:
        error = error.text.strip()
        if 'Video not found, deleted or abused, sorry!' in error or "Video not found or deleted. We're sorry!" in error:
            ctx.set_offline()
        elif 'This video might not work properly or is still in the conversion queue' in error:
            ctx.temporary_unavailable(msg='video is converting', seconds=300)
        else:
            ctx.plugin_out_of_date('unknown error: {}'.format(error))

def get_download_url(ctx, resp):
    url = resp.soup.find('iframe', src=lambda e: e.startswith('http://play.flashx.tv/')).get('src')
    resp = resp.get(url)

    try:
        url = resp.soup.find('a', href=lambda e: e.startswith('http://play.flashx.tv/player/fxtv.php?')).get('href')
    except AttributeError:
        form = resp.soup.find('form', action=lambda a: a == 'view.php' or a == 'show.php')
        action, data = hoster.serialize_html_form(form)
        resp = resp.post(action, data=data)
    else:
        resp = resp.get(url)
    check_errors(ctx, resp)

    #ctx.account.get('http://play.flashx.tv/player/soy.php', referer=resp.url)
    m = re.search('"(http.*?config=(http://play.flashx.tv/nuevo/player/[^/\?]+.php\?str=[^"]+))', resp.content)
    url = m.group(1)
    config_url = m.group(2)
    resp = resp.get(url)
    resp = resp.get(config_url)
    return resp.soup.find('file').text.strip()

def on_check_http(file, resp):
    check_errors(file, resp)
    name = resp.soup.find('div', 'video_title').text.strip()+'.flv'
    url = get_download_url(file, resp)
    hoster.check_download_url(file, url, name=name)
    
def on_download(chunk):
    resp = chunk.account.get(chunk.url)
    return get_download_url(chunk, resp)
