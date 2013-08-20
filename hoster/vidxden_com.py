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
    name = "vidxden.com"
    can_resume_free = True
    max_chunks_free = 2
    patterns = [
        hoster.Matcher('https?', '*.'+name, '!/file/<id>', type='|type'),
    ]
    config = [
        hoster.cfg('original', True, bool, description='Crawl the original file if available'),
        hoster.cfg('mobile', True, bool, description='Crawl the mobile version if available'),
        hoster.cfg('stream', True, bool, description='Crawl the stream version')
    ]

    has_captcha_free = False

def get_original_url(chunk, resp):
    url = re.search(r'<a href="(/get_file\.php\?id=[^"]+)', resp.text)
    if url:
        return hoster.urljoin(resp.url, url.group(1))

def get_mobile_url(chunk, resp):
    url = re.search(r'<a href="(/mobile/file/[^"]+)', resp.text)
    if url:
        url = hoster.urljoin(resp.url, url.group(1))
        resp = chunk.account.get(url)
        url = re.search(r'<a href="(/get_file\.php\?id=[^"]+)', resp.text)
        if url:
            return hoster.urljoin(resp.url, url.group(1))

def get_stream_url(chunk, resp):
    url = re.search("playlist: '(\/get_file\.php\?stream=[^\']+)", resp.text).group(1)
    url = hoster.urljoin(resp.url, url)

    resp = chunk.account.get(url, referer=resp.url)

    s = BeautifulSoup(resp.text.replace('media:content', 'mediacontent'))
    url = s.find('mediacontent')[0].get('url')

    return hoster.urljoin(resp.url, url)

functions = dict(original=get_original_url, mobile=get_mobile_url, stream=get_stream_url)

def check_errors(ctx, text):
    if u"This file doesn't exist" in text:
        ctx.set_offline()

def go_to_download_page(ctx, resp):
    s = BeautifulSoup(resp.text)
    form = s.select('form input[name="confirm"]')[0].find_parent('form')
    action, data = hoster.serialize_html_form(form)
    ctx.wait(1)
    return ctx.account.post(ctx.url, data=data, referer=resp.url)


def on_check(file):
    if file.pmatch.type:
        file.set_infos()
        return

    resp = file.account.get(file.url)
    check_errors(file, resp.text)

    s = BeautifulSoup(resp.text)
    tname = s.select('.site-content h1')
    if not tname:
        # TODO: send plugin out of date error
        file.set_offline()

    name = tname[0].text.strip()
    name = re.sub(r'\s*\([^\)]*\)\s*$', '', name)
    name, ext = os.path.splitext(name)

    if not file.account.premium:
        resp = go_to_download_page(file, resp)

    def _get(type, ext):
        try:
            url = functions[type](file, resp)
            if url:
                r = file.account.get(url, stream=True)
                r.close()
                links.append(dict(url=file.url+'?type='+type, name=name+'.'+ext, size=r.headers['Content-Length']))
        except:
            pass

    links = []
    if this.config.original:
        _get('original', ext[1:])
    if this.config.mobile:
        _get('mobile', 'mp4')
    if this.config.stream:
        _get('stream', 'flv')

    if not links and not this.config.stream:
        _get('stream', 'flv')
    if not links and not this.config.mobile:
        _get('mobile', 'mp4')
    if not links and not this.config.original:
        _get('original', ext[1:])
    if not links:
        file.fatal('found no possible downloads')

    core.add_links(links)
    file.delete_after_greenlet()

def on_download_premium(chunk):
    resp = chunk.account.get(chunk.url)
    check_errors(chunk, resp.text)
    return functions[chunk.pmatch.type](chunk, resp)

def on_download_free(chunk):
    resp = chunk.account.get(chunk.url)
    check_errors(chunk, resp.text)
    resp = go_to_download_page(chunk, resp)
    return functions[chunk.pmatch.type](chunk, resp)


extra_persistent_account_columns = ['_auth']

def on_initialize_account(account, retry=0):
    if not account.username:
        account.premium = False
        return

    if account._auth:
        account.cookies['auth'] = account._auth
        resp = account.get('http://www.'+this.name+'/profile.php?pro', allow_redirects=False)
        if resp.status_code == 200:
            account._check(resp)
            return

    resp = account.get('http://www.'+this.name+'/authenticate.php?login')
    if resp.status_code != 200:
        account.retry('website currently out of order', 60)

    data = {"user": account.username, "pass": account.password, "remember": 1, "login_submit": "Login"}
    m = re.search(r'<img src="(/include/captcha\.php\?_CAPTCHA[^"]+)', resp.text)
    if m:
        url = hoster.urljoin(resp.url, m.group(1).replace('&amp;', '&'))
        r = account.get(url, referer=resp.url)
        if r.status_code != 200:
            account.retry('website currently out of order', 60)
        mime = r.headers['Content-Type'] or 'image/png'
        data['captcha_code'] = account.solve_captcha_text(data=r.content, mime=mime, retries=1, timeout=90).next()
    
    resp = account.post(resp.url, referer=resp.url, data=data)
    if 'Please re-enter the captcha code' in resp.text:
        if retry < 3:
            return account.on_initialize(retry + 1)
        else:
            account.fatal('login failed (captcha input failed)')

    if 'auth' not in account.cookies:
        account.login_failed()

    account._auth = account.cookies['auth']

    resp = account.get('http://www.'+this.name+'/profile.php?pro', allow_redirects=False)
    account._check(resp)

def _check(account, resp):
    m = re.search(r'<td>Pro\s*Status\s*</td>\s*<td>(Free|Active)', resp.text, re.DOTALL)
    if not m:
        account.fatal('error parsing account page')
    account.premium = m.group(1) == 'Active' and True or False

    if account.premium:
        m = re.search(r'<td>Expiring\s*</td>\s*<td>([^<]*)</td>', resp.text, re.DOTALL)
        if not m:
            account.fatal('error parsing account page')
        account.expires = m.group(1)
