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
    model = hoster.HttpPremiumHoster
    name = 'sendspace.com'
    patterns = [
        hoster.Matcher('https?', '*.sendspace.com', '!/file/<id>')
    ]
    url_template = 'http://www.sendspace.com/file/{id}'

def on_initialize_account(account):
    if not account.username:
        return
    data = {
        "action": "login",
        "submit": "login",
        "target": "%2F",
        "action_type": "login",
        "remember": "1",
        "username": account.username,
        "password": account.password,
        "remember": "on"}
    resp = account.post('http://www.sendspace.com/login.html', data=data)
    if 'ssal' not in account.cookies:
        account.login_failed()
    type = resp.soup.find(id='userType').text.strip()
    if type == 'Lite':
        account.premium = False
    else:
        account.log.debug('userType is {}. assuming premium'.format(type))
        account.premium = True

def check_errors(ctx, resp):
    error = resp.soup.find('div', 'error')
    if error:
        error = error.text.strip()
        if 'Sorry, the file you requested is not available' in error:
            ctx.set_offline()
        elif 'You cannot download more than one file at a time' in error:
            ctx.only_one_connection_allowed()
        elif 'You may now download the file' in error:
            ctx.temporary_unavailable(seconds=30)
        elif 'full capacity' in error:
            ctx.temporary_unavailable(seconds=300)
        elif 'this connection has reached the' in error:
            ctx.ip_blocked(seconds=3600, need_reconnect=True)
        elif 'reached daily download' in error:
            # TODO: calculate seconds till next day
            ctx.ip_blocked(seconds=3600, need_reconnect=True)
        elif 'The file is not currently available' in error or 'Our support staff have been notified and we hope to resolve the problem shortly' in error:
            ctx.temporary_unavailable(seconds=3600)
        else:
            ctx.plugin_out_of_date(error)

def on_check_http(file, resp):
    check_errors(file, resp)
    name = resp.soup.select('div.info h2 b')[0].text.strip()
    size = resp.soup.find('div', 'file_description')
    size.find('b').extract()
    size = size.text.strip().strip('"').strip()
    file.set_infos(name, approx_size=size)

def on_download_free(chunk):
    resp = chunk.account.get(chunk.url)
    check_errors(chunk, resp)
    url = resp.soup.find(id='download_button').get('href')
    return url

def on_download_premium(chunk):
    # TODO: check if this is correct
    return chunk.url
