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
    name = 'putlocker.com'
    uses = 'sockshare.com'
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
    config = config
    favicon_url = "http://www.putlocker.com/putlocker.ico"

    has_captcha_free = False
