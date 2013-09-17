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
from PIL import JpegImagePlugin

@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    name = 'sharebeast.com'
    patterns = [
        hoster.Matcher('https?', '*.sharebeast.com', '!/<id>')
    ]
    url_template = 'http://www.sharebeast.com/{id}'
    favicon_url = "http://sub.sharebeast.com/favicon.ico"

def on_initialize_account(account):
    account.cookies['lang'] = 'english'
    if not account.username:
        return
    data = {
        "op": "login",
        "login": account.username,
        "password": account.password
    }
    resp = account.post('http://www.sharebeast.com/cgi-bin/datapage.cgi', data=data)
    result = resp.text.split('#@#@')
    if result[0] != 'success':
        account.login_failed()
    account.cookies['xfss'] = result[2]
    account.cookies['login'] = account.username
    # TODO: fetch account infos

def check_errors(ctx, resp, name):
    found = list()
    for error in (resp.soup.find('h2'), resp.soup.find('p', 'err')):
        if not error:
            continue
        error = error.text.strip()
        if not error or error == name:
            continue
        if 'File Not Found' in error or 'No such file' in error or 'The file was removed by' in error:
            ctx.set_offline()
        elif 'This server is in maintenance mode' in error:
            ctx.maintenance()
        elif 'You have reached the download-limit' in error:
            ctx.ip_blocked(seconds=300, need_reconnect=True)
        elif "You're using all download slots for IP" in error:
            ctx.ip_blocked(seconds=300, need_reconnect=True)
        elif "Error happened when generating Download Link" in error:
            ctx.temporary_unavailable(seconds=60)
        elif 'Please Buy Premium To download this file' in error or 'This file reached max downloads limit' in error:
            ctx.premium_needed()
        found.append(error)
    if found:
        ctx.plugin_out_of_date(' / '.join(found))

def on_check_http(file, resp):
    try:
        name = resp.soup.find('div', 'tite').find('h2').text.strip()
    except AttributeError:
        name = None
    check_errors(file, resp, name)
    if name is None:
        file.parse_error('filename')
    size = resp.soup.find('div', 'inlinfo', text='Size').find_next('div', 'inlinfo1').text.strip()
    file.set_infos(name=name, approx_size=size)

def on_download_free(chunk, retry=1):
    resp = chunk.account.get(chunk.url, use_cache=True)
    check_errors(chunk, resp, chunk.file.name)
    form = resp.soup.find('form', attrs=dict(name='F1'))
    action, data = hoster.serialize_html_form(form)
    if 'password' in data:
        data['password'] = chunk.solve_password(retries=1).next()
    resp = chunk.account.post(chunk.url, data=data, allow_redirects=False)
    if 'Location' not in resp.headers:
        error = resp.soup.find('p', 'err')
        if error:
            do_retry = False
            if 'Wrong password' in error:
                do_retry = True
            if do_retry and retry <= 3:
                return on_download_free(chunk, retry + 1)
        check_errors(chunk, resp, chunk.file.name)
        file.no_download_link()
    return resp.headers['Location']
