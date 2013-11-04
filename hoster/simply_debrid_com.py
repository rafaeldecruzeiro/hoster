# encoding: utf-8
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

import time
from dateutil import parser

from ... import hoster


@hoster.host
class this:
    name = "simply-debrid.com"
    model = hoster.MultiHttpHoster
    favicon_url = 'http://simply-debrid.com/fav.png'
    can_resume = True
    # max_chunks = 1


def on_check(file):
    link = unrestrict(file, file.url)
    hoster.check_download_url(file, link)

    
def on_download_premium(chunk):
    return unrestrict(chunk.file, chunk.url)


def api(account, **kwargs):
    kwargs["u"] = account.username
    kwargs["p"] = account.password
    return account.get("http://simply-debrid.com/api.php", params=kwargs)


def on_initialize_account(account):
    if not account.username:
        return

    resp = api(account, login=2)

    if resp.text == u'01: invalid login':
        account.login_failed()

    x = map(unicode.strip, resp.text.split(";"))
    if len(x) < 3:
        account.login_failed()

    account.premium = bool(int(x[0]))
    if not account.premium:
        account.fatal("no premium")
    account.expires = time.mktime(parser.parse(x[2], dayfirst=True).timetuple())

    resp = api(account, list=1)
    account.set_compatible_hosts(filter(bool, resp.text.strip(u" ;").split(u";")))


def unrestrict(file, url, clear=False):
    resp = api(file.account, dl=url)
    t = resp.content
    file.log.debug("simply-debrid unrestrict: {}".format(t))
    if "Invalid link" in t or ("API" in t and "ERROR" in t) or not t.startswith("http"):
        file.fatal(t)
    return t
