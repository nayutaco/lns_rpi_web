#!/usr/bin/env python
# coding:utf-8

import requests
from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler
import urllib.parse
import configparser
import base64

config = configparser.ConfigParser()
config.read('/home/pi/Prog/bin/rpi_config.ini')

WEBDIR = config.get('PATH', 'WEBDIR')
KEY = 'ptarm:ptarm'     #TODO: change after!!

authkey = ''


def start(port, callback):
    global authkey

    authkey = base64.b64encode(KEY.encode()).decode()

    def handler(*args):
        CallbackServer(callback, *args)
    server = HTTPServer(('', int(port)), handler)
    server.serve_forever()

class CallbackServer(BaseHTTPRequestHandler):
    def __init__(self, callback, *args):
        self.callback = callback
        BaseHTTPRequestHandler.__init__(self, *args)

    def do_GET(self):
        getkey= str(self.headers.get('Authorization'))
        if getkey == None:
            self.do_AUTHHEAD()
            self.wfile.write(b'no auth header received')
        elif getkey == 'Basic ' + authkey:
            self.send_response(200)
            self.end_headers()

            parsed_path = urllib.parse.urlparse(self.path)
            query = parsed_path.query
            mode = 'r'
            if len(query) == 0:
                fname = self.path[1:]
                if fname == '':
                    fname = 'index.html'
                elif fname.endswith('favicon.png'):
                    mode = 'rb'
                fname = WEBDIR + '/' + fname
                #print('fname=' + fname)
                with open(fname, mode) as f:
                    message = f.read()
            else:
                with open(WEBDIR + '/result1.html') as f:
                    message = f.read()
                message += self.callback(query)
                with open(WEBDIR + '/result2.html') as f:
                    message += f.read()
            if mode == 'r':
                self.wfile.write(message.encode('utf-8'))
            else:
                self.wfile.write(message)
        else:
            self.do_AUTHHEAD()
            self.wfile.write(getkey.encode())
            self.wfile.write(b'not authenticated')


    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header(
            'WWW-Authenticate', 'Basic realm="Ptarmigan Login"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()


