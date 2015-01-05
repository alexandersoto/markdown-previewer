#!/usr/bin/python

import base64
import json
import os
import SimpleHTTPServer
import SocketServer
import sys
import thread
import time
import urllib2

# TODO add arguments for these values - use argparse
HOST = 'localhost'
PORT = 0
GITHUB_API_ROOT = 'https://api.github.com'
CSS_URL = 'https://raw.githubusercontent.com/sindresorhus/github-markdown-css/\
gh-pages/github-markdown.css'
CSS = None


def get_github_css():
    """
    Returns the latest github css.
    From: https://github.com/sindresorhus/github-markdown-css
    """

    # Reference it globally so that we only download the CSS once
    global CSS
    if CSS is not None:
        return CSS
    else:
        print "Downloading CSS...",
        response = urllib2.urlopen(CSS_URL)
        print "done!"
        CSS = response.read()

    return CSS


def markdown_to_html(markdown_file_path):
    """
    Converts a markdown file to HTML using GitHub's API
    https://developer.github.com/v3/markdown/
    """

    print "Converting markdown...",
    markdown_api_endpoint = '/markdown'
    url = GITHUB_API_ROOT + markdown_api_endpoint

    data = {
        'text': open(markdown_file_path).read(),
        'mode': 'markdown'
    }
    data = json.dumps(data)
    request = urllib2.Request(url, data, {'Content-Type': 'application/json'})

    if 'GITHUB_API_TOKEN' in os.environ:
        user = os.environ['GITHUB_API_TOKEN']
        base64string = base64.encodestring('{user}:'.format(user=user)).replace('\n', '')
        request.add_header("Authorization", "Basic {base64}".format(base64=base64string))

    response = urllib2.urlopen(request)
    print "done!"

    # Display rate limiting information to user
    request_limit = int(response.info().get('X-RateLimit-Limit'))
    requests_remaining = int(response.info().get('X-RateLimit-Remaining'))
    reset_time = int(response.info().get('X-RateLimit-Reset'))
    time_remaining = time_to_readable_delta_string(reset_time)
    print 'You have {requests_remaining:,} requests to the GitHub API remaining. \
You will be allowed {request_limit:,} more requests in {time_remaining}.'.format(
        requests_remaining=requests_remaining,
        request_limit=request_limit,
        time_remaining=time_remaining)

    return response.read()


def time_to_readable_delta_string(seconds):
    """
    Given a UTC timestamp, return the time until that date in a human readable form.
    The form is: A days, B hours, C minutes, D seconds.
    """
    seconds = int(seconds) - int(time.time())
    delta_time = {}
    delta_time['days'] = seconds // 86400
    delta_time['hours'] = seconds // 3600 % 24
    delta_time['minutes'] = seconds // 60 % 60
    delta_time['seconds'] = seconds % 60

    # Return a string accounting for plurals
    def get_plural_string(delta_time_resolution, value):
        if value > 1:
            return '{value:,} {time_resolution}'.format(value=value,
                                                        time_resolution=delta_time_resolution)
        elif value == 1:
            return '1 ' + delta_time_resolution[:-1]
        else:
            return ''
    human_readable_string = ''

    # Sorted alphabetical order turns out to be numeric ordering (days - hours - minutes - seconds)
    for resolution in sorted(delta_time.keys()):
        string = get_plural_string(resolution, delta_time[resolution])
        if len(string):
            human_readable_string += string + ', '

    return human_readable_string.strip(', ')


def make_html(title, css, body):

    # Using .format() makes this gross and requires double {{ everywhere, but it's lightweight
    # TODO: Think of a better solution
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title> {title} </title>
        <style>
            body {{
                margin: 0;
                padding: 40px;
            }}
            {css}
        </style>
    </head>
    <body>
        <div class="markdown-body">
            {body}
        </div>
    </body>
    <script>
        'use strict';
        var CONTENT_URL = '/body';
        var $body = document.getElementsByClassName('markdown-body')[0];

        var getUrlAjax = function(url, success, error) {{

            // youmightnotneedjquery.com
            var request = new XMLHttpRequest();
            request.open('GET', url, true);
            request.onload = function() {{
                if (request.status >= 200 & request.status < 400) {{
                    success(request.responseText);
                }} else {{
                    error(request.status);
                }}
            }};
            request.onerror = error;
            request.send();
        }}

        var updateContent = function(content) {{
            if ($body.innerHTML !== content) {{
                $body.innerHTML = content;
            }}
        }};

        window.setInterval(function() {{
            getUrlAjax(CONTENT_URL, updateContent);
        }}, 100);
    </script>
    </html>
    """.format(title=title, css=css, body=body)
    return html


class Server:
    """ A server that will respond with given html on given host:port """

    def __init__(self, host, port):
        class MyRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

            def log_message(self, format, *args):
                """ Silence logging requests as our ajax makes it noisy """
                pass

            def do_GET(self):
                if self.path == '/body':
                    response = self.body
                else:
                    response = self.html

                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.send_header("Content-length", len(response))
                self.end_headers()
                self.wfile.write(response)

        self.handler = MyRequestHandler
        self.thread = None

        # Let's us restart the server without having to wait for the port to be unblocked
        SocketServer.TCPServer.allow_reuse_address = True

        self.server = SocketServer.TCPServer((host, port), self.handler)
        self.host, self.port = self.server.server_address

    def start(self):
        self.thread = thread.start_new_thread(self.server.serve_forever, ())

    def stop(self):
        if self.thread is not None:
            self.thread.exit()

    def restart(self):
        self.stop()
        self.start()

    def set_file(self, file_path):
        title = os.path.basename(file_path)
        css = get_github_css()
        body = markdown_to_html(file_path)

        self.handler.body = body
        self.handler.html = make_html(title, css, body)

    def set_html(self, html):
        self.handler.html = html

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit("Usage: ./markdown_previewer.py MARKDOWN_FILE_TO_WATCH")

    file_name = sys.argv[1]
    file_path = os.path.abspath(os.path.join(os.getcwd(), file_name))

    # Create and start the web server
    print "Starting server..."
    server = Server(HOST, PORT)
    server.set_file(file_path)
    server.start()
    print("Serving {file_path} on {host}:{port}".format(file_path=file_path,
                                                        host=server.host, port=server.port))

    # Watch file for changes, and update the html if there is one
    last_modified = os.stat(file_path).st_ctime
    while True:
        time.sleep(.1)
        new_last_modified = os.stat(file_path).st_ctime
        if new_last_modified > last_modified:
            print file_path + " changed, converting markdown."
            server.set_file(file_path)
            last_modified = new_last_modified
