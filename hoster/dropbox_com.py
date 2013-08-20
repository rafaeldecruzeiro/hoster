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
    name = 'dropbox.com'
    favicon_url = 'https://www.dropbox.com/static/images/favicon-vflonlsct.ico'
    patterns = [
        hoster.Matcher('https', '*.dropbox.com', "!/s/<id>/<name>").set_tag("direct"),
    ]

def normalize_url(url, pmatch):
    return url.replace("://www.", "://dl.", 1)

def on_check(file):
    hoster.check_download_url(file, file.url)
    
def on_download(chunk):
    return chunk.url
