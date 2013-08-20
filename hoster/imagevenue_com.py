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
    name = 'imagevenue.com'
    patterns = [
        hoster.Matcher('https?', '*.imagevenue.com', '!/gallery/<loc>/<id>.php').set_tag('gallery'),
        hoster.Matcher('https?', '*.imagevenue.com', '!/img.php', image="name").set_tag('image')
    ]
    use_check_cache = False

def infos(file):
    name = re.sub('^\d+_(.*)_\d+lo(\.[^\.+])', '\\1\\2', file.pmatch.name)
    file.set_infos(name=name)

def on_check(file):
    if file.pmatch.tag == 'gallery':
        resp = file.account.get(file.url)
        try:
            title = resp.soup.find('font', color='grey').text.strip()
            title = re.sub('\s*#\d+', '', title)
        except:
            title = None
        links = [hoster.urljoin(file.url, l.get('href')) for l in resp.soup.find_all('a') if l.text.strip() != '<< Prev']
        return dict(links=links, package_name=title)
    else:
        infos(file)

def on_download(chunk):
    resp = chunk.account.get(chunk.url)
    try:
        url = resp.soup.find('img', id='thepic').get('src')
    except AttributeError:
        if 'This image does not exist on this server' in resp.text:
            chunk.file.set_offline()
        raise
    return hoster.urljoin(chunk.url, url)
