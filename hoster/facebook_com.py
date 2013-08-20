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

# -*- coding: utf-8 -*-

import re
import json

from ... import hoster
from ...plugintools import between

@hoster.host
class this:
    model = hoster.HttpHoster
    name = 'facebook.com'
    patterns = [
        hoster.Matcher('https?', '*.facebook.com', '!/video/video.php', v="id"),
        hoster.Matcher('https?', '*.facebook.com', '!/photo.php', v="id")
    ]
    config = [
        hoster.cfg("low_only", False, bool, description="Prefer low quality")
    ]
    url_template = "https://facebook.com/video/video.php?v={id}"

def getdata(text):
    data = between(text, '[["params",', ']')
    data = json.loads(data)
    data = json.loads(re.sub(r"\%([A-F0-9]{2})", lambda n: chr(int(n.group(1), 16)), data))
    data = data["video_data"][0]
    if not data["hd_src"] or this.config.low_only:
        return data["sd_src"]
    else:
        return data["hd_src"]

def on_check(file):
    resp = file.account.get(file.url)
    title = resp.soup.find("h2", attrs={"class": "uiHeaderTitle"})
    if not title:
        file.no_download_link()
    else:
        name = title.text+".mp4"
        file.set_infos(name=name)
    vid = getdata(resp.text)
    hoster.check_download_url(file, vid, name=name)

def on_download(chunk):
    resp = chunk.account.get(chunk.url)
    return getdata(resp.text)

def on_initialize_account(self):
    self.set_user_agent()
    self.cookies["locale"] = "en_GB"
