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
    name = '2shared.com'
    patterns = [
        hoster.Matcher('https?', '*.2shared.com', '!/file/<id>/<name>.html')
    ]
    url_template = 'http://www.2shared.com/file/{id}/{name}.html'

def on_check_http(file, resp):
    if 'The file link that you requested is not valid' in resp.text:
        file.set_offline()
    name = resp.soup.find('h1').text.strip()
    size = resp.soup.select('table.box td.c div.body')[1]
    size = re.search('File size:</span>\s*([^\s]+ [^\s]+)', unicode(size), re.DOTALL).group(1).strip()
    file.set_infos(name, size=size)

def on_download(chunk, retry=1):
    resp = chunk.account.get(chunk.url, use_cache=True)
    form = resp.soup.find('form', attrs=dict(name='redDCForm'))
    action, data = hoster.serialize_html_form(form)
    action = hoster.urljoin(resp.url, action)
    resp = chunk.account.post(action, referer=resp.url, data=data, stream=True)
    return resp.soup.find('a', href=lambda a: '2shared.com/download/' in a if a else False).get('href')
