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
import time

from ... import hoster, account

#from ...config import globalconfig
#config = globalconfig.new('hoster').new('rapidshare.com')
#config['server'] = None
#Cogent;Deutsche Telekom;Level(3);Level(3) #2;GlobalCrossing;Level(3) #3;Teleglobe;GlobalCrossing #2;TeliaSonera #2;Teleglobe #2;TeliaSonera #3;TeliaSonera", "Preferred Server", "None

class Account(account.HttpPremiumAccount):
    API_URL = "http://api.rapidshare.com/cgi-bin/rsapi.cgi"

    def get_account_details(self):
        params = {"sub": "getaccountdetails", "type": "prem", "login": self.username, "password": self.password, "withcookie": 1}
        resp = self.get(self.API_URL, params=params)
        if resp.text.startswith('ERROR'):
            error = resp.text[len('ERROR')+1:].strip()
            if "access flood" in error:
                self.retry(error, 30)
            self.fatal(error)

        data = {}
        ff = filter(lambda a: a and True or False, resp.text.split('\n'))
        for f in ff:
            k, v = f.split('=', 1)
            data[k] = v

        return data

    def on_initialize(self):
        self.cookies = {"lang": "en", "country": "US"}

        if not self.username:
            return

        details = self.get_account_details()
        self.cookies['enc'] = details['cookie']

        self.expires = int(details['billeduntil'])
        self.premium = time.time() < self.expires and True or False

    def _request(self, fn, *args, **kwargs):
        if not 'cookies' in kwargs:
            kwargs['cookies'] = dict()
        kwargs['cookies'].update(self.cookies)
        return fn(self, *args, **kwargs)

    def get(self, *args, **kwargs):
        return self._request(account.HttpPremiumAccount.get, *args, **kwargs)

    def post(self, *args, **kwargs):
        return self._request(account.HttpPremiumAccount.post, *args, **kwargs)


@hoster.host
class this:
    model = hoster.HttpPremiumHoster
    account_model = Account
    name = 'rapidshare.com'
    patterns = [
        hoster.Matcher('https?', '*.rapidshare.com', r'/(?:files/(?P<id>\d*?)/(?P<name>[^?]+)|#!download\|(?:\w+)\|(?P<id_new>\d+)\|(?P<name_new>[^|]+))'),
    ]

def normalize_url(url, pmatch):
    pmatch.id = pmatch.id or pmatch.id_new
    pmatch.name = pmatch.name or pmatch.name_new
    return 'http://rapidshare.com/files/{}/{}'.format(pmatch.id, pmatch.name)

def check_file(file, exc):
    params = {"sub": "checkfiles", "files": file.pmatch.id, "filenames": file.pmatch.name, "incmd5": 1}
    resp = file.account.get('https://api.rapidshare.com/cgi-bin/rsapi.cgi', params=params)

    if resp.text.startswith('ERROR'):
        if "access flood" in resp.text:
            file.retry(resp.text, 30)
        file.fatal(resp.text)

    data = dict()
    data['id'], data['name'], data['size'], data['server_id'], data['status'], data['host'], data['md5'] = resp.text.strip().split(',', 7)

    data['size'] = int(data['size'])
    data['status'] = int(data['status'])
    data['md5'] = data['md5'].lower()

    if data['status'] in (0, 4, 5):
        exc.set_offline('file is offline')
    elif data['status'] == 3:
        exc.temporary_unavailable(90)
    elif not data['status'] in (1, 2):
        exc.plugin_out_of_date(msg='unknown api response')

    return data

def on_check(file):
    data = check_file(file, file)

    if 'md5' in data and data['md5']:
        htype, hvalue = 'md5', data['md5']
    else:
        htype, hvalue = None, None

    file.set_infos(name=data['name'], size=data['size'], hash_type=htype, hash_value=hvalue)
    
def on_download_premium(chunk):
    data = check_file(chunk.file, chunk)
    url = "http://rs{server_id}{host}.rapidshare.com/files/{id}/{name}?directstart=1".format(**data)
    resp = chunk.account.get(url, stream=True, chunk=chunk)
    if not 'Content-Disposition' in resp.headers:
        error = resp.text.splitlines()[0]
        chunk.fatal(error)
    return resp

def on_download_free(chunk):
    data = check_file(chunk.file, chunk)

    while True:
        data = free_wait(chunk, data)
        if data:
            break

    url = "http://{}/cgi-bin/rsapi.cgi".format(data['host'])
    params = {"sub": "download", "editparentlocation": 0, "bin": 1, "fileid": data['id'], "filename": data['name'], "dlauth": data['auth']}
    resp = chunk.account.get(url, params=params, stream=True)
    if not "Content-Disposition" in resp.headers:
        check_response(resp.text, chunk)
        chunk.plugin_out_of_date(msg='unknown download error')

    return resp

def check_response(text, chunk):
    if "You need RapidPro to download more files from your IP address" in text:
        chunk.account.ip_blocked(60, need_reconnect=True)
    elif "Too many users downloading from this server right now" in text or "All free download slots are full" in text:
        chunk.temporary_unavailable(120)
    elif "This file is too big to download it for free" in text:
        chunk.premium_needed()
    elif "Filename invalid." in text:
        chunk.fatal('filename is invalid')
    elif "Download permission denied by uploader." in text:
        chunk.fatal('download is not permitted by uploader')

def free_wait(chunk, file_data):
    params = {"sub": "download", "fileid": file_data['id'], "filename": file_data['name'], "try": "1", "cbf": "RSAPIDispatcher", "cbid": "1"}
    resp = chunk.account.get("https://api.rapidshare.com/cgi-bin/rsapi.cgi", params=params)

    check_response(resp.text, chunk)

    wait = re.search("You need to wait (\d+) seconds", resp.text)
    if wait:
        wait = int(wait.group(1))
        if wait > 600:
            chunk.retry('waiting for download slot', wait, need_reconnect=True)
        chunk.wait(wait)
    else:
        tmp, info = resp.text.split(":")
        data = info.split(",")
        # id ?
        retval = {"id": chunk.pmatch.id, "name": file_data["name"], "host": data[0], "auth": data[1], "server": file_data["server_id"], "size": file_data["size"]}
        chunk.wait(int(data[2]) + 2)
        return retval
