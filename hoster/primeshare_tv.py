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

from ... import hoster

@hoster.host
class this:
    model = hoster.HttpHoster
    name = 'primeshare.tv'
    patterns = [
        hoster.Matcher('https?', ['*.primeshare.tv'], '!/download/<id>'),
    ]
    favicon_url = "http://static.primeshare.tv/images/favicon.ico"

def on_initialize_account(self):
    self.set_user_agent('ipad')

def get_download_url(ctx, resp):
    try:
        src = resp.soup.select('video source')[0].get('src')
    except IndexError:
        error = resp.soup.find('h1').text
        if 'The File does not exists' in error:
            ctx.set_offline()
        else:
            ctx.plugin_out_of_date(error.strip())
    else:
        return src

def on_check_http(file, resp):
    src = get_download_url(file, resp)
    hoster.check_download_url(file, src)

def on_download(chunk):
    resp = chunk.account.get(chunk.url, use_cache=True)
    return get_download_url(file, resp)
