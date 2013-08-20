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
    name = 'imageshack.us'
    patterns = [
        hoster.Matcher('https?', '*.imageshack.us', '/photo/my-images/(?P<srv>\d+)/(?P<name>.*)/').set_tag('page')
    ]

def on_check_http(file, resp):
    return [resp.soup.find(id='direct-link').get('value')]
