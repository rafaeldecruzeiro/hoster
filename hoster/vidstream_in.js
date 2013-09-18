/*
Copyright (C) 2013 COLDWELL AG

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
*/

plugin.this = {
    model: 'HttpPremiumHoster',
    name: "vidstream.in",
    can_resume_free: true,
    max_chunks_free: 2,
    patterns: [
        matcher('https?', '*.vidstream.in', '!/<id>'),
    ],
    has_captcha_free: false
};

function check_errors(ctx, resp) {
    if(resp.text.contains('The file you were looking for could not be found'))
        ctx.set_offline();
}

plugin.on_check_http = function(file, resp) {
    check_errors(file, resp);
    try {
        name = resp.soup.select('h2')[0].text.match(/Watch (.*?) online/)[1];
    }
    catch(e) {
        console.log(resp.text);
        throw e;
    }
    name = name.replace(/\s*mp4\s*$/, '')
    file.set_infos({name: name+'.mp4'});
};

plugin.on_download_free = function(chunk) {
    resp = chunk.account.get(chunk.url);
    check_errors(chunk, resp);
    resp = xfilesharing_download(resp, 1, true)[0]();
    check_errors(chunk, resp);
    return resp.text.match(/file: "([^"]+)"/)[1];
};
