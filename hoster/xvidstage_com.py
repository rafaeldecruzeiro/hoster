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
from ... import hoster, javascript
from ...plugintools import between

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'xvidstage.com'
    patterns = [
        hoster.Matcher('https?', '*.xvidstage.com', '!/<id>'),
    ]
    can_resume_free = True
    max_filesize_free = hoster.GB(2)
    max_filesize_premium = hoster.GB(2)

def check_errors(ctx, resp):
    if 'File Not Found' in resp.text:
        ctx.set_offline()

def on_check_http(file, resp):
    check_errors(file, resp)
    content = resp.soup.find("div", attrs={"id": "content"})
    if file.account.premium:
        raise NotImplementedError('premium is untested')
        # TODO: untested, 1:1 copy of ryushare.com
        t = content.find("table", attrs={"class": "file_slot"})
        if not t:
            error = content.find("b").text
            if error == "File not Found":
                file.set_offline()
            else:
                file.fatal(error)
            return
        name = t.find("td", attrs={"nowrap": "nowrap"}).text
        size = between(t.find("small").text, "(", ")")
        file.set_infos(name=name, size=size.split(" ")[0])
    else:
        name = content.find("h2").text.strip().replace("Download File", "").strip()
        size = between(content.find("font").text, "(", ")").strip()
        file.set_infos(name=name, approx_size=size)

def on_download_premium(chunk):
    raise NotImplementedError('premium is untested')
    resp = chunk.account.get(chunk.url, allow_redirect=False)
    if "Location" in resp.headers:
        return resp.headers["Location"]
    _, payload = hoster.serialize_html_form(resp.soup.find(attrs={"name": "F1"}))
    payload["down_direct"] = 1
    resp = chunk.account.post(chunk.url, data=payload)
    return resp.soup.find("div", attrs={"id": "content"}).find("a")["href"]

def on_download_free(chunk):
    resp = chunk.account.get(chunk.url, use_cache=True)
    check_errors(file, resp)
    action, data = hoster.serialize_html_form(resp.soup.find_all("form")[-1])
    resp = chunk.account.post(chunk.url, data=data)
    s = filter(lambda a: a.text.strip() != '', resp.soup.select('#player_code script'))[0]
    result = javascript.execute('''
        result = '';
        document = {};
        document.write = function(x) { result += x; }
        SWFObject = function(x) { SWFObject.x = x; };
        SWFObject.params = {};
        SWFObject.prototype.addParam = function(a, b) { SWFObject.params[a] = b; };
        SWFObject.prototype.addVariable = function(a, b) { SWFObject.params[a] = b; };
        SWFObject.prototype.write = function(y) { SWFObject.y = y; };
        ''' + s.text + ''';
        SWFObject.params["file"] || result;
        ''')
    if result.startswith('<object'):
        result = re.search(r'<param\s*name="src"\s*value="([^"]+)"', result).group(1)
    return result

def on_initialize_account(account):
    account.cookies['lang'] = 'english'
    if account.username:
        # TODO: implement accounts. use code from junocloud.me or ryushare.com
        raise NotImplementedError('premium is untested, also login it not working on website')
