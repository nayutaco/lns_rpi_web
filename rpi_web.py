from flask import Flask, render_template, request, Markup, send_file, send_from_directory, redirect, url_for, session, make_response
from flask_httpauth import HTTPDigestAuth
from waitress import serve

import os
from time import sleep
import datetime
from collections import OrderedDict
from glob import glob
import configparser
import json
import socket
import sys
import subprocess
import threading
import traceback
import urllib.request, urllib.parse, urllib.error
import urllib.parse
import random
import logging                                                                  
import logging.handlers 
import io

config = configparser.SafeConfigParser()

PROGDIR = ''
PTARMDIR = ''
NODEDIR = ''
WEBDIR = ''
STATIC = ''
COPYNODEDIR = ''
PROGVER = ''
PTARMVER = ''
BINVER = ''
EPAPERVER = ''
UARTVER = ''
WEBVER = ''
EXE_GET_INVOICE = ''
LOG_FILE = ''

# table row
TABLE_ROW_COL0 = '#f8f8f8'
TABLE_ROW_COL1 = '#f0f0f0'

app = Flask(__name__)
auth = HTTPDigestAuth()


def config_init(conf_path):
    global PROGDIR, PTARMDIR, NODEDIR, WEBDIR, STATIC, COPYNODEDIR,\
            PROGVER, PTARMVER, BINVER, EPAPERVER, UARTVER, WEBVER,\
            EXE_GET_INVOICE, LOG_FILE

    config.read(conf_path)

    PROGDIR = config.get('PATH', 'PROGDIR')
    PTARMDIR = config.get('PATH', 'PTARMDIR')
    NODEDIR = config.get('PATH', 'NODEDIR')
    WEBDIR = config.get('PATH', 'WEBDIR')
    STATIC = config.get('PATH', 'STATIC')
    COPYNODEDIR = config.get('PATH', 'COPYNODEDIR')
    PROGVER = config.get('PATH', 'PROGVER')
    PTARMVER = config.get('PATH', 'PTARMVER')
    BINVER = config.get('PATH', 'BINVER')
    EPAPERVER = config.get('PATH', 'EPAPERVER')
    UARTVER = config.get('PATH', 'UARTVER')
    WEBVER = config.get('PATH', 'WEBVER')

    # don't forget last space!!
    EXE_GET_INVOICE = 'bash ' + PROGDIR + '/bin/get_invoice.sh '

    LOG_FILE = WEBDIR + "/logs/rpiweb.log"

def flask_init():
    app.secret_key = 'seacret_key'
    app.config['SECRET_KEY'] = str(random.random())

    # Add RotatingFileHandler to Flask Logger
    handler = logging.handlers.RotatingFileHandler(LOG_FILE, "a+", maxBytes=1000000, backupCount=5)
    logging.basicConfig(level=logging.INFO)
    handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s'))
    app.logger.addHandler(handler)

@auth.get_password
def get_pw(id):
    app.logger.info('GET_AUTH')
    pwfile = STATIC + '/digest.txt'
    with open(pwfile) as i:
        id_list = json.load(i)
        if id in id_list:
            return id_list.get(id)
    return None

@app.before_request 
@auth.login_required 
def before_request():
    pass

def prepare_response(data):
    response = make_response(data)
    response.headers['X-XSS-Protection'] = 0
    app.logger.info(response.headers)
    return response

def socket_send(req):
    app.logger.info(req + ' start')
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(('localhost', 9736))
    client.send(req.encode('utf-8'))
    response = client.recv(4096)
    client.close()
    app.logger.info(req + ' success')
    return response

class SubprocessError(Exception):
    pass

def linux_cmd_subprocess(cmd):
    app.logger.info('[' + cmd + ']' + ' start')
    ret = ''
    try:
        ret = subprocess.run(cmd, shell=True, stdout = subprocess.PIPE, stderr=subprocess.STDOUT, check=True)#.stdout
        app.logger.info('[' + cmd + ']' + ' success')
    except subprocess.CalledProcessError as e:
        app.logger.error('[' + cmd + ']' + ' failed')
        app.logger.error(e.output.decode('utf8'))
        raise SubprocessError(cmd)
    return ret.stdout.decode('utf8')

def show_channel(json_chan, closed=False):
    try:
        app.logger.info('SHOW_CHANNEL start')
        result = '<table class="u-full-width"><caption>'
        if closed:
            result += 'closed '
        result += '</caption><thead><tr class="headline"><th class="headtd">name</th><th>value</th></tr></thead><tbody>'

        ITEMS = [
            # [ 'JSON key', 'label', 'type 0=str, 1=int, 2=bool, 99=NEXT', 'NEXT JSON key', 'NEXT type' ]
            ['peer_node_id', 'node id', 0],
            ['status', 'status', 0],
            ['channel_id', 'channel id', 0],
            ['short_channel_id', 'short channel id', 99, 'str', 0],
            ['local_msat', 'local msat', 1],
            ['remote_msat', 'remote msat', 1],
            ['feerate_per_kw', 'feerate per kw', 1],
            ['funding_local', 'funding txid', 99, 'funding_txid', 0],
            ['funding_local', 'funding vout', 99, 'funding_txindex', 1],
            ['last_confirm', 'confirmation', 1],
            ['state', 'funder', 99, 'is_funder', 2],
            ['commit_info_local', 'dust limit sat', 99, 'dust_limit_sat', 1],
            ['commit_info_local', 'max htlc value in flight msat', 99, 'max_htlc_value_in_flight_msat', 1],
            ['commit_info_local', 'channel reserve sat', 99, 'channel_reserve_sat', 1],
            ['commit_info_local', 'htlc minimum msat', 99, 'htlc_minimum_msat', 1],
            ['commit_info_local', 'to self delay', 99, 'to_self_delay', 1],
            ['commit_info_local', 'max accepted htlcs', 99, 'max_accepted_htlcs', 1],
            ['commit_info_remote', 'dust limit sat', 99, 'dust_limit_sat', 1],
            ['commit_info_remote', 'max htlc value in flight msat', 99, 'max_htlc_value_in_flight_msat', 1],
            ['commit_info_remote', 'channel reserve sat', 99, 'channel_reserve_sat', 1],
            ['commit_info_remote', 'htlc minimum msat', 99, 'htlc_minimum_msat', 1],
            ['commit_info_remote', 'to self delay', 99, 'to_self_delay', 1],
            ['commit_info_remote', 'max accepted htlcs', 99, 'max_accepted_htlcs', 1],
        ]

        idlist = []

        def conv(chan, cntl, item):
            val = ''
            if cntl == 1:
                val = str(chan[item])
            elif cntl == 2:
                val = 'YES' if chan[item] != 0 else 'no'
            else:
                val = chan[item]
            return val
        def tr(bgcolor, item, value):
            try:
                if item == 'funding txid':
                    dirinfo = linux_cmd_subprocess('ls /boot')
                    if 'RPI_MAINNET' in dirinfo:
                        return '<tr class="headtd"><td>' + item + '</td><td>' + '<a href="https://www.smartbit.com.au/tx/' + value + '" target="_blank">' + value + '</a>' + '</td></tr>'
                    else:
                        return '<tr class="headtd"><td>' + item + '</td><td>' + '<a href="https://testnet.smartbit.com.au/tx/' + value + '" target="_blank">' + value + '</a>' + '</td></tr>'
                elif item == 'feerate per kw':
                    return '<tr><td class="headtd">' + item + '</td><td>' + str('{:,}'.format(int(value))) + ' (sat/kweight)</td></tr>'
                elif item == 'local msat':
                    return '<tr><td class="headtd">' + 'local' + '</td><td>' + str('{:,}'.format(int(value))) + ' (msat)</td></tr>'
                elif item == 'remote msat':
                    return '<tr><td class="headtd">' + 'remote' + '</td><td>' + str('{:,}'.format(int(value))) + ' (msat)</td></tr>'
                elif item == 'confirmation':
                    return '<tr><td class="headtd">' + item + '</td><td>' + str('{:,}'.format(int(value))) + '</td></tr>'
                elif item == 'funding vout':
                    return '<tr><td class="headtd">' + item + '</td><td>' + str('{:,}'.format(int(value))) + '</td></tr>'
                elif item == 'dust limit sat':
                    return '<tr><td class="headtd" style="padding-left: 40px;">' + 'dust limit' + '</td><td>' + str('{:,}'.format(int(value))) + ' (sat)</td></tr>'
                elif item == 'max htlc value in flight msat':
                    return '<tr><td class="headtd" style="padding-left: 40px; padding-right: 10px;" >' + 'max htlc value in flight' + '</td><td>' + str('{:,}'.format(int(value))) + ' (msat)</td></tr>'
                elif item == 'channel reserve sat':
                    return '<tr><td class="headtd" style="padding-left: 40px;">' + 'channel reserve' + '</td><td>' + str('{:,}'.format(int(value))) + ' (sat)</td></tr>'
                elif item == 'htlc minimum msat':
                    return '<tr><td class="headtd" style="padding-left: 40px;">' + 'htlc minimum' + '</td><td>' + str('{:,}'.format(int(value))) + ' (msat)</td></tr>'
                elif item == 'to self delay':
                    return '<tr><td class="headtd" style="padding-left: 40px;">' + item + '</td><td>' + str('{:,}'.format(int(value))) + '</td></tr>'
                elif item == 'max accepted htlcs': 
                    return '<tr><td class="headtd" style="padding-left: 40px;">' + item + '</td><td>' + str('{:,}'.format(int(value))) + '</td></tr>'
                else:
                    return '<tr><td class="headtd">' + item + '</td><td>' + value + '</td></tr>'
            except:
                return ''
        index = 0
        for chan in json_chan['channel_info']:
            bgcolor = TABLE_ROW_COL0 if index % 2 == 0 else TABLE_ROW_COL1
            index += 1
            for item in ITEMS:
                val = ''
                if item[2] == 99:
                    val = conv(chan[item[0]], item[4], item[3])
                else:
                    val = conv(chan, item[2], item[0])
                if not closed and item[1] == 'status':
                    idindex = index - 1
                    val += ' <form action="/list2.html" method="POST"><button class="closebutton" name="idselect" value="' + str(idindex) + ' mutual">Mutual close</button>' \
                           ' <button class="closebutton" name="idselect" value="' + str(idindex) + ' force">Force close</button></form></td></tr>'
                    idlist.append(chan['peer_node_id'])
                if item[0] == 'commit_info_local' and item[1] == 'dust limit sat':
                    result += '<tr><td class="headtd">commit info local</td><td></td></tr>'
                if item[0] == 'commit_info_remote' and item[1] == 'dust limit sat':
                    result += '<tr><td class="headtd">commit info remote</td><td></td></tr>'
                result += tr(bgcolor, item[1], val)
            result += '<tr style="height: 15px; border-bottom:1px solid #b6b6b6;"><td></td><td></td></tr>'
        result += '</tbody></table>'
        app.logger.info('SHOW_CHANNEL success')
    except Exception as e:
        app.logger.error('SHOW_CHANNEL failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return result, idlist

def callback_createinvoice(params):
    try:
        app.logger.info('CREATE_INVOICE start')

        linux_cmd_subprocess('sudo rm -f ' + PROGDIR + '/invoice.txt')
        linux_cmd_subprocess('sudo rm -f ' + PROGDIR + '/invoice.png')

        th = threading.Thread(target=linux_cmd_subprocess, args=(EXE_GET_INVOICE + str(params.strip()),), name='invoice')
        th.start()

        cmd = 'rm -rf ' + STATIC + '/qr'
        linux_cmd_subprocess(cmd)
        cmd = 'mkdir ' + STATIC + '/qr'
        linux_cmd_subprocess(cmd)

        sleep(5)

        cmd = 'cat ' + PROGDIR + '/invoice.txt'
        bolt11 = linux_cmd_subprocess(cmd)
        date = "{0:%Y%m%d%H%M%S}".format(datetime.datetime.now()) + '.png'
        dir = STATIC + '/qr/' + date + ' '
        cmd = 'qrencode -s 3 -m 1 --foreground=b6b6b6 --background=232727 -o ' + dir + bolt11
        linux_cmd_subprocess(cmd)
        result = '<p></p><a href="#"><img src="./static/qr/' + date + '"></a>'
        result += '<p class="bolt11">' + bolt11 + '<p>'

    except Exception as e:
        app.logger.error('CREATE_INVOICE failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return result

def callback_emptywallet(params):
    result = ''
    try:
        app.logger.info('EMPTYWALLET start')
        req = '{"method":"emptywallet","params":["' + params + '"]}'
        response = socket_send(req)
        app.logger.info(response)

        jrpc = json.loads(response.decode('utf-8'))
        app.logger.info(jrpc)
        try:
            if 'result' in jrpc:
                result = jrpc['result']
            elif 'error' in jrpc:
                app.logger.error('error')
                app.logger.error('code='  + str(jrpc['error']['code']))
                app.logger.error('message=' + jrpc['error']['message'])
                result = 'NG: ' + jrpc['error']['message']
        except:
            result = 'exception'
    except socket.error as exc:
        app.logger.error('EMPTYWALLET failed')
        app.logger.error("Caught exception socket.error : %s" % exc)
        result = 'Can\'t connect ptarmigan.'
    return result

def callback_connect(params):
    result = ''
    try:
        app.logger.info('CONNECT start')
        connstr = params.strip()
        req = '{"method":"connect","params":["' + connstr + '","",0,0 ]}'
        response = socket_send(req)
        app.logger.info(response)

        jrpc = json.loads(response.decode('utf-8'))
        app.logger.info(jrpc)
        try:
            if 'result' in jrpc:
                result = jrpc['result']
            elif 'error' in jrpc:
                app.logger.error('error')
                app.logger.error('code='  + str(jrpc['error']['code']))
                app.logger.error('message=' + jrpc['error']['message'])
                result = 'NG: ' + jrpc['error']['message']
        except:
            result = 'exception'
        app.logger.info('CONNECT success')
    except socket.error as exc:
        app.logger.error('CONNECT failed')
        app.logger.error("Caught exception socket.error : %s" % exc)
        result = 'Can\'t connect ptarmigan.'
    return result

def callback_close_mutual(params):
    try:
        app.logger.info('CLOSE_MUTUAL start')
        req = '{"method":"close","params":["' + params + '","0.0.0.0",0 ]}'
        response = socket_send(req)
        app.logger.info(response)

        jrpc = json.loads(response.decode('utf-8'))
        app.logger.info(jrpc)
        try:
            if 'result' in jrpc:
                result = 'OK: ' + jrpc['result']
            elif 'error' in jrpc:
                app.logger.error('error')
                app.logger.error('code='  + str(jrpc['error']['code']))
                app.logger.error('message=' + jrpc['error']['message'])
                result = 'NG: ' + jrpc['error']['message']
        except:
            result = 'exception'
        app.logger.info('CLOSE_MUTUAL success')
    except socket.error as exc:
        app.logger.error('CLOSE_MUTUAL failed')
        app.logger.error("Caught exception socket.error : %s" % exc)
        result = 'Can\'t connect ptarmigan.'
    return result

def callback_close_force(params):
    try:
        app.logger.info('CLOSE_FORCE start')
        req = '{"method":"close","params":["' + params + '","0.0.0.0",0,"force" ]}'
        response = socket_send(req)
        app.logger.info(response)

        jrpc = json.loads(response.decode('utf-8'))
        app.logger.info(jrpc)
        try:
            if 'result' in jrpc:
                result = 'OK: ' + jrpc['result']
            elif 'error' in jrpc:
                app.logger.error('error')
                app.logger.error('code='  + str(jrpc['error']['code']))
                app.logger.error('message=' + jrpc['error']['message'])
                result = 'NG: ' + jrpc['error']['message']
        except:
            result = 'exception'
        app.logger.info('CLOSE_FORCE success')
    except socket.error as exc:
        app.logger.error('CLOSE_FORCE failed')
        app.logger.error("Caught exception socket.error : %s" % exc)
        result = 'Can\'t connect ptarmigan.'
    return result

def wpa_supplicant(ssid, password):    
    cmd = ['sudo', 'sh', '-c', WEBDIR + '/wifipass.sh ' + ssid + ' ' + password]
    ret = ''
    try:
        app.logger.info('WiFi_SETTING start')
        subprocess.check_output(cmd).strip()
        ret = 'OK'
        app.logger.info('WiFi_SETTING success')
    except subprocess.CalledProcessError as e:
        app.logger.error('WiFi_SETTING failed')
        app.logger.error('!!! error happen(errcode=%d) !!!' % e.returncode)
        ret = 'NG'
    return ret

def callback_getinfo():
    idlist = []
    try:
        app.logger.info('GETINFO start')
        response = socket_send('{"method":"getinfo","params":[]}')
        jrpc = json.loads(response.decode('utf-8'))
        result = '<table class="u-full-width"><caption>Local Information</caption><thead><tr class="headline"><th class="headtd">name</th><th>value</th></tr></thead><tbody>'
        result += '<tr><td class="headtd">node id</td><td>' + jrpc['result']['node_id'] + '</td></tr>'
        result += '<tr><td class="headtd">total</td><td>' + str('{:,}'.format(jrpc['result']['total_local_msat'])) + ' (msat)</td></tr>'
        result += '</tbody></table><br>'
        result += '<table class="u-full-width"><caption>Channel Information</caption><thead><tr class="headline"><th class="headtd">name</th><th>value</th></tr></thead><tbody>'
        index = 0
        
        for prm in jrpc['result']['peers']:
            bgcolor = TABLE_ROW_COL0 if index % 2 == 0 else TABLE_ROW_COL1
            result += '<tr style="border-top: 1px solid #b6b6b6;"><td class="headtd">node id</td><td>' + prm['node_id'] + '</td></tr>'

            result += '<tr><td class="headtd">status</td><td>' + prm['status'] + '</td></tr>'

            result += '<tr><td class="headtd">funding tx</td><td>'
            try:
                dirinfo = linux_cmd_subprocess('ls /boot')
                if 'RPI_MAINNET' in dirinfo:
                    result += '<a href="https://www.smartbit.com.au/tx/' + prm['funding_tx'] + '" target="_blank">' + prm['funding_tx'] + '</a>' + ':' + str(prm['funding_vout'])
                else:
                    result += '<a href="https://testnet.smartbit.com.au/tx/' + prm['funding_tx'] + '" target="_blank">' + prm['funding_tx'] + '</a>' + ':' + str(prm['funding_vout'])
            except:
                result += '---'
            result += '</td></tr>'

            result += '<tr><td class="headtd">local</td><td>'
            try:
                result += str('{:,}'.format(prm['local']['msatoshi'])) + ' (msat)'
            except:
                result += '---'
            result += '</td></tr>'

            result += '<tr><td class="headtd">remote</td><td>'
            try:
                result += str('{:,}'.format(prm['remote']['msatoshi'])) + ' (msat)'
            except:
                result += '---'
            result += '</td></tr>'

            result += '<tr><td class="headtd">feerate</td><td>'	
            try:            	
                result += str('{:,}'.format(prm['feerate_per_kw'])) + ' (sat/kweight)'
            except:	
                result += '---'
            result += '</td></tr>'

            result += '<tr><td class="headtd">confirmation</td><td>'	
            try:            	
                result += str('{:,}'.format(prm['confirmation']))
            except:	
                result += '---'
            result += '</td></tr>'

            try:            	
                annosig  = '<tr><td class="headtd">announcement</td><td>'	
                annosig += prm['announcement_signatures']
                annosig += '</td></tr>'
                result += annosig
            except:	
                pass

            result += '<tr><td class="headtd">connect</td><td>'
            try:
                if prm['role'] == 'client':
                    result += 'connected'
                else:
                    result += 'disconnected'
            except:
                result += '---'
            result += '</td></tr>'
            result += '<tr style="height: 15px; border-bottom:1px solid #b6b6b6;"><td></td><td></td></tr>'
            
            index += 1
            idlist.append(prm['node_id'])
        result += '</tbody></table>'
        app.logger.info('GETINFO success')
    except socket.error as exc:
        app.logger.error('GETINFO failed')
        app.logger.error("Caught exception socket.error : %s" % exc)
        result = 'Can\'t connect ptarmigan.'
    return result, idlist

def callback_getchannel():
    try:
        app.logger.info('GETCHANNEL start')
        cmd = PTARMDIR + '/showdb -s -d ' + NODEDIR
        json_chan = json.loads(linux_cmd_subprocess(cmd))
        result = show_channel(json_chan)
        app.logger.info('GETCHANNEL success')
    except Exception as e:
        app.logger.error('GETCHANNEL failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return result

def callback_closed_channel():
    def tr(bgcolor, num, item):
        try:
            return '<tr><td class="headtd" style="width:15%">' + num + '</td><td>' +\
                    '<form action="/list3.html" method="POST"><button class="linkbutton" name="idselect" value=' + num + '>' + item + '</button></form></td></tr>'
        except:
            return ''

    try:
        app.logger.info('SHOWCLOSEDCHANNEL start')
        cmd = PTARMDIR + '/showdb --listclosed -d ' + NODEDIR
        json_chan = json.loads(linux_cmd_subprocess(cmd))

        result = '<table class="u-full-width">'
        result += '<thead><tr class="headline"><th>index</th><th>channel id</th></tr></thead>'
        result += '<tbody>'
        index = 0
        itemlist = []
        for chan in json_chan:
            itemlist.append(chan)
            bgcolor = TABLE_ROW_COL0 if index % 2 == 0 else TABLE_ROW_COL1
            index += 1
            result += tr(bgcolor, str(index), chan)

        result += '</tbody></table>'
        app.logger.info('SHOWCLOSEDCHANNEL success')
    except Exception as e:
        app.logger.error('SHOWCLOSEDCHANNEL failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))  
    return result, itemlist

def callback_listinvoice():
    try:
        app.logger.info('LISTINVOICE start')

        cmd = 'rm -rf ' + STATIC + '/qr'
        linux_cmd_subprocess(cmd)

        cmd = 'mkdir ' + STATIC + '/qr'
        linux_cmd_subprocess(cmd)

        cmd = PTARMDIR + '/ptarmcli --listinvoice | jq \'.result | sort_by(.creation_time) | reverse\''
        response = linux_cmd_subprocess(cmd)
        jrpc = json.loads(response)
        imgindex = 0
        result = '<table class="u-full-width"><caption></caption><thead><tr class="headline"><th class="headtd">name</th><th>value</th></tr></thead><tbody>'
        for inv in jrpc:
            result += '<tr><td class="headtd">payment hash</td><td>' + inv['hash'] + '</td></tr>'
            result += '<tr><td class="headtd">state</td><td>' + inv['state'] + '</td></tr>'
            result += '<tr><td class="headtd">amount</td><td>' + str('{:,}'.format(inv["amount_msat"])) + ' (msat)</td></tr>'
            result += '<tr><td class="headtd">creation time</td><td>' + inv['creation_time'] + '</td></tr>'
            result += '<tr><td class="headtd">expiry</td><td>' + str('{:,}'.format(inv["expiry"])) + ' (sec)' + '</td></tr>'

            dir = STATIC + '/qr/' + str(imgindex) + '.png '
            cmd = 'qrencode -s 3 -m 1 --foreground=b6b6b6 --background=232727 -o ' + dir + inv['bolt11']
            linux_cmd_subprocess(cmd) 
            result += '<tr><td class="headtd">bolt11</td><td style="word-break: break-word;white-space: normal;">' + inv['bolt11'] + '</td></tr>'
            result += '<tr><td class="headtd"></td><td style="text-align: right;"><a href="#"><img id="' + str(imgindex) + '" src="./static/qr/' + str(imgindex) + '.png"></a></td>'
            result += '<tr style="height: 15px; border-bottom:1px solid #b6b6b6;"><td></td><td></td</tr>'
            imgindex += 1
        result += '</tbody></table>'
        app.logger.info('LISTINVOICE success')
    except Exception as e:        
        app.logger.error('LISTINVOICE failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
        result = 'Can\'t connect ptarmigan.'
    return result

def callback_get1stlayerinfo():
    try:
        app.logger.info('GET_1ST_LAYER_INFO start')
        response = socket_send('{"method":"getbalance","params":[]}')
        jrpc = json.loads(response.decode('utf-8'))
        result = '<table class="u-full-width"><caption></caption><thead><tr class="headline"><th></th><th></th></tr></thead><tbody>'
        result += '<tr><td class="headtd">balance</td><td>' + str('{:,}'.format(jrpc['result'])) + ' (sat)' + '</td></tr>'

        response = socket_send('{"method":"getnewaddress","params":[]}')
        jrpc = json.loads(response.decode('utf-8'))
        result += '<tr><td class="headtd">receive address</td><td>' + jrpc['result'] + '</td></tr>'
        app.logger.info('GET_1ST_LAYER_INFO success')
    except socket.error as exc:
        app.logger.error('GET_1ST_LAYER_INFO failed')
        app.logger.error("Caught exception socket.error : %s" % exc)
        result = 'Can\'t connect ptarmigan.'
    return result

def client():
    try:
        app.logger.info('CHANGE_CLIENTMODE start')
        linux_cmd_subprocess('sudo touch /boot/RPI_CLIENT')
        linux_cmd_subprocess('bash ' + PROGDIR + '/bin/wifi_setting.sh')
        app.logger.info('CHANGE_CLIENTMODE success')
    except Exception as e:        
        app.logger.error('CHANGE_CLIENTMODE failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return 

def apmode():
    try:
        app.logger.info('CHANGE_APMODE start')
        linux_cmd_subprocess('sudo touch /boot/RPI_APMODE')
        linux_cmd_subprocess('bash ' + PROGDIR + '/bin/wifi_setting.sh')
        app.logger.info('CHANGE_APMODE success')
    except Exception as e: 
        result = 'Failed'
        app.logger.error('CHANGE_APMODE failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return

def blockchainnetworkchange():
    try:
        app.logger.info('CHANGE_BLOCKCHAIN_NETWORK start')
        dirinfo = linux_cmd_subprocess('ls /boot')
        if 'RPI_MAINNET' in dirinfo:
            linux_cmd_subprocess('sudo rm /boot/RPI_MAINNET')
            msg = 'OK: Changed Testnet.'
        else:
            linux_cmd_subprocess('sudo touch /boot/RPI_MAINNET')
            msg = 'OK: Changed Mainnet.'
        app.logger.info('CHANGE_BLOCKCHAIN_NETWORK success')
    except Exception as e: 
        msg = 'NG'
        app.logger.error('CHANGE_BLOCKCHAIN_NETWORK failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return msg
    
def deviceinfo():
    try:
        app.logger.info('DEVICEINFO start')
        #User
        pwfile = STATIC + '/digest.txt'
        with open(pwfile) as i:
            id_list = json.load(i)
            id_list = list(id_list.keys())
            user = id_list[0]

        #IP address
        ip = linux_cmd_subprocess('hostname -I')

        #hostname
        hn = linux_cmd_subprocess('hostname')

        #SD card ammount
        cmd = 'df / -h'
        result = linux_cmd_subprocess(cmd)
        result = result.split()

        maxsize = result[8]
        usedsize = result[9]

        #WiFi SSID
        cmd = 'iwconfig wlan0'
        ssid = linux_cmd_subprocess(cmd)
        ssid = ssid.split()
        ssid = ssid[3].split(':')
        ssid = str(ssid[1]).strip('"')
        app.logger.info('DEVICEINFO success')

    except Exception as e:        
        ip = ''
        maxsize = ''
        usedsize = ''
        ssid = ''
        hn = ''
        user = ''

        app.logger.error('DEVICEINFO failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))

    #version
    ver_prog = '---'
    ver_ptarm = '---'
    ver_bin = '---'
    ver_epaper = '---'
    ver_uart = '---'
    ver_web = '---'
    try:
        with open(PROGVER) as f:
            ver_prog = f.read()
    except:
        pass
    try:
        with open(PTARMVER) as f:
            ver_ptarm = f.read()
    except:
        pass
    try:
        with open(BINVER) as f:
            ver_bin = f.read()
    except:
        pass
    try:
        with open(EPAPERVER) as f:
            ver_epaper = f.read()
    except:
        pass
    try:
        with open(UARTVER) as f:
            ver_uart = f.read()
    except:
        pass
    try:
        with open(WEBVER) as f:
            ver_web = f.read()
    except:
        pass

    return ip, maxsize, usedsize, ssid, hn, user,\
            ver_prog, ver_ptarm, ver_bin, ver_epaper, ver_uart, ver_web

def showclosed(value):
    try:
        app.logger.info('SHOWCLOSED start')
        cmd = PTARMDIR + '/showdb --showclosed ' + value +  ' -d ' + NODEDIR
        jrpc = json.loads(linux_cmd_subprocess(cmd), object_pairs_hook=OrderedDict)
        result = '<table class="u-full-width"><caption style="margin-bottom: 30px;">NODE: ' + value + '</caption><thead><tr class="headline"><th class="headtd">name</th><th>value</th></tr></thead><tbody>'
        info = jrpc['channel_info'][0]
        #outputinfo = ['peer_node_id', 'channel_id', ]

        for prm in info:
            value = info[prm]
            if type(value) is OrderedDict:
                result += '<tr class="grayborder"><td class="headtd">' + str(prm.replace('_', ' ')) + '</td><td>'
                index = 0
                for a in value:
                    if index != 0:
                        if a == 'dust_limit_sat' :
                            result += '<br />' + 'dust limit' + ':' + str('{:,}'.format(value[a])) + ' (sat)'
                        elif a == 'max_htlc_value_in_flight_msat' :
                            result += '<br />' + 'max htlc value in flight' + ':' + str('{:,}'.format(value[a])) + ' (msat)'
                        elif a == 'channel_reserve_sat' :
                            result += '<br />' + 'channel reserve' + ':' + str('{:,}'.format(value[a])) + ' (sat)'
                        elif a == 'htlc_minimum_msat' :
                            result += '<br />' + 'htlc minimum' + ':' + str('{:,}'.format(value[a])) + ' (msat)'
                        else :
                            result += '<br />' + str(a.replace('_', ' ')) + ':' + str(value[a]).replace('OrderedDict', '')
                    else:
                        if a == 'dust_limit_sat' :
                            result += 'dust limit' + ':' + str('{:,}'.format(value[a])) + ' (sat)'
                        elif a == 'max_htlc_value_in_flight_msat' :
                            result += 'max htlc value in flight' + ':' + str('{:,}'.format(value[a])) + ' (msat)'
                        elif a == 'channel_reserve_sat' :
                            result += 'channel reserve' + ':' + str('{:,}'.format(value[a])) + ' (sat)'
                        elif a == 'htlc_minimum_msat' :
                            result += 'htlc minimum' + ':' + str('{:,}'.format(value[a])) + ' (msat)'
                        else :
                            result += str(a.replace('_', ' ')) + ':' + str(value[a]).replace('OrderedDict', '')
                    index += 1
                result += '</td></tr>'
            else:
                if prm == 'local_msat' :
                    result += '<tr class="grayborder"><td class="headtd">' + 'local' + '</td><td>' + str('{:,}'.format(value)) + ' (msat)</td></tr>'
                elif prm == 'remote_msat' :
                    result += '<tr class="grayborder"><td class="headtd">' + 'remote' + '</td><td>' + str('{:,}'.format(value)) + ' (msat)</td></tr>'
                elif prm == 'funding_satoshis' :
                    result += '<tr class="grayborder"><td class="headtd">' + 'funding' + '</td><td>' + str('{:,}'.format(value)) + ' (sat)</td></tr>'
                elif prm == 'feerate_per_kw' :
                    result += '<tr class="grayborder"><td class="headtd">' + 'feerate' + '</td><td>' + str('{:,}'.format(value)) + ' (sat/kweight)</td></tr>'
                else:
                    result += '<tr class="grayborder"><td class="headtd">' + str(prm.replace('_', ' ')) + '</td><td>' + str(value) + '</td></tr>'
        result += '</tbody></table>'
        app.logger.info('SHOWCLOSED success')
    except Exception as e:        
        result = 'Failed'
        app.logger.error('SHOWCLOSED failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return result

def backup():
    try:
        app.logger.info('BACKUP start')
        try:
            os.chdir(NODEDIR)
            linux_cmd_subprocess('sudo systemctl stop rpi_ptarm')
            sleep(3)
        except:
            app.logger.info('"ptarmd" has already stopped.')

        os.chdir(PROGDIR)
        cmd = 'sudo rm -rf ' + PROGDIR + '/backup/'
        linux_cmd_subprocess(cmd)
        cmd = 'mkdir ' + PROGDIR + '/backup'
        linux_cmd_subprocess(cmd)
        
        #remove recently file
        cmd = 'sudo rm -f ' + PROGDIR + '/lnshield_backup_*'
        linux_cmd_subprocess(cmd)

        #mainnet DB
        cmd_main = 'tar cf ' + PROGDIR + '/backup/main.tar ' + '-C ' + COPYNODEDIR + ' mainnet'
        linux_cmd_subprocess(cmd_main)

        #testnet DB
        cmd_test = 'tar cf ' + PROGDIR + '/backup/test.tar ' + '-C ' + COPYNODEDIR + ' testnet'
        linux_cmd_subprocess(cmd_test)

        #wifi setting file
        cmd = 'sudo cp /etc/wpa_supplicant/wpa_supplicant.conf ' + PROGDIR + '/backup/wpa_supplicant.conf'
        linux_cmd_subprocess(cmd)

        #blockchain network setting
        dirinfo = linux_cmd_subprocess('ls /boot')
        if 'RPI_MAINNET' in dirinfo:
            cmd = 'cp /boot/RPI_MAINNET ' + PROGDIR + '/backup'
            linux_cmd_subprocess(cmd)

        #all files compress
        date = "{0:%Y%m%d%H%M%S}".format(datetime.datetime.now()) + '.tar.gz'
        hostname = linux_cmd_subprocess('hostname').strip()
        filename = 'lnshield_backup_' + hostname + '_' + date
        cmd = 'sudo tar zcf ' + filename + ' -C ' + PROGDIR + ' backup'
        linux_cmd_subprocess(cmd)

        cmd = 'sudo rm -rf ' + PROGDIR + '/backup/'
        linux_cmd_subprocess(cmd)

        cmd = 'ls ' + PROGDIR
        dirinfo = linux_cmd_subprocess(cmd)
        if date in dirinfo:
            result = '<p style="margin-bottom: 0px;">Backup has completed.</p>' 
            result += '<p style="margin: 0px;">Please download "'+ filename +'".</p>' 
            result += '<p style="margin-bottom: 0px;">[ATTENTION]</p>'
            result += '<p style="margin-top: 0px;">When you press download, it executes initializing DB.</p>'
            result += '<a href="/send_backupfile"><button class="sendbutton">Download</button></a>'
            app.logger.info('BACKUP success')
        else:
            result = 'NG'
            app.logger.error('BACKUP failed')
    except Exception as e:        
        result = 'NG'
        app.logger.error('BACKUP failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return result

def restore():
    try:
        app.logger.info('RESTORE start')

        try:
            os.chdir(NODEDIR)
            linux_cmd_subprocess('sudo systemctl stop rpi_ptarm')
            sleep(3)
        except:
            app.logger.info('"ptarmd" has already stopped.')

        os.chdir(PROGDIR)
        cmd = 'sudo rm -rf ' + PROGDIR + '/backup/'
        linux_cmd_subprocess(cmd)
        cmd = 'find ' + PROGDIR + '/ -maxdepth 1 -type f -name "*.tar.gz" -exec tar zxf {} \;' 
        linux_cmd_subprocess(cmd)
        
        #bak
        linux_cmd_subprocess('mv '+ COPYNODEDIR + '/mainnet ' + COPYNODEDIR + '/mainnet.bak')
        linux_cmd_subprocess('mv '+ COPYNODEDIR + '/testnet ' + COPYNODEDIR + '/testnet.bak')
        linux_cmd_subprocess('sudo mv /etc/wpa_supplicant/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant.conf.bak')

        #mainnet
        linux_cmd_subprocess('tar xf '+ PROGDIR + '/backup/main.tar ' + '-C ' + COPYNODEDIR)

        #testnet
        linux_cmd_subprocess('tar xf ' + PROGDIR + '/backup/test.tar ' + '-C ' + COPYNODEDIR)

        #wifi
        linux_cmd_subprocess('sudo mv ' + PROGDIR + '/backup/wpa_supplicant.conf /etc/wpa_supplicant')

        #blockchain network
        cmd = 'ls ' + PROGDIR + '/backup'
        dirinfo = linux_cmd_subprocess(cmd)
        if 'RPI_MAINNET' in dirinfo:
            linux_cmd_subprocess('sudo mv ' + PROGDIR + '/backup/RPI_MAINNET /boot')

        linux_cmd_subprocess('sudo rm -rf ' + PROGDIR + '/backup/')
        linux_cmd_subprocess('sudo rm -rf ' + PROGDIR + '/logfiles/')
        linux_cmd_subprocess('sudo rm -rf ' + PROGDIR + '/*.tar.gz')
        linux_cmd_subprocess('rm -rf '+ COPYNODEDIR + '/mainnet.bak')
        linux_cmd_subprocess('rm -rf ' + COPYNODEDIR + '/testnet.bak')
        linux_cmd_subprocess('sudo rm -f /etc/wpa_supplicant/wpa_supplicant.conf.bak')

        result = '<p style="margin-bottom: 0px;">Restore has completed.</p>' + '<p style="margin-top: 0px;">It needs to reboot with Client mode.</p>'
        app.logger.info('RESTORE success')
    except Exception as e:        
        result = 'NG: Restore Failed'
        app.logger.error('RESTORE failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))

        #recovery
        linux_cmd_subprocess('rm -rf '+ COPYNODEDIR + '/mainnet')
        linux_cmd_subprocess('rm -rf ' + COPYNODEDIR + '/testnet')
        linux_cmd_subprocess('sudo rm -f /etc/wpa_supplicant/wpa_supplicant.conf')
        linux_cmd_subprocess('mv '+ COPYNODEDIR + '/mainnet.bak ' + COPYNODEDIR + '/mainnet')
        linux_cmd_subprocess('mv '+ COPYNODEDIR + '/testnet.bak ' + COPYNODEDIR + '/testnet')
        linux_cmd_subprocess('sudo mv /etc/wpa_supplicant/wpa_supplicant.conf.bak /etc/wpa_supplicant/wpa_supplicant.conf')
    return result

def upload():
    result = '<form action="/upload" enctype="multipart/form-data" method="POST" style="margin-top: 24px;">' + '<input type="file" accept="application/gzip" name="bkfile" class="inputcustom" required>' + '<input type="submit"  value="Upload">'
    return result

def paytowalletlist():
    try:
        app.logger.info('PAYTOWALLETLIST start')
        os.chdir(NODEDIR)
        cmd = PTARMDIR + '/ptarmcli --paytowallet=0'
        json_chan = json.loads(linux_cmd_subprocess(cmd))
        json_chan = json_chan['result']
        jwallet = json_chan['wallet']
        jlist = json_chan['list']
        result = '<table class="u-full-width"><caption>Ptarmigan Wallet Info</caption><thead><tr class="headline"><th class="headtd">name</th><th>value</th></tr></thead><tbody>'
        result += '<tr><td class="headtd">amount</td><td>' + str('{:,}'.format(jwallet['amount'])) + ' (sat)</td></tr>'
        result += '<tr><td class="headtd">messege</td><td>' + jwallet['message'] + '</td></tr>'
        result += '</tbody></table><br>'

        result += '<table class="u-full-width"><caption>Wait List</caption><thead><tr class="headline"><th class="headtd">name</th><th>value</th></tr></thead><tbody>'
        for value in jlist:
            result += '<tr><td class="headtd">type</td><td>' + value['type'] + '</td></tr>'
            result += '<tr><td class="headtd">outpoint</td><td>' + value['outpoint'] + '</td></tr>'
            result += '<tr><td class="headtd">amount</td><td>' + str('{:,}'.format(value['amount'])) + ' (sat)</td></tr>'
            result += '<tr><td class="headtd">state</td><td>' + value['state'] + '</td></tr>'    
            result += '<tr style="height: 15px; border-bottom:1px solid #b6b6b6;"><td></td><td></td</tr>'
        result += '</tbody></table>'
        app.logger.info('PAYTOWALLETLIST success')
    except Exception as e:        
        result = 'Failed'
        app.logger.error('PAYTOWALLETLIST failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return result    

def paytowallet():
    try:
        app.logger.info('PAYTOWALLET start')
        os.chdir(NODEDIR)
        cmd = PTARMDIR + '/ptarmcli --paytowallet=1'
        linux_cmd_subprocess(cmd)
        msg = '<p style="margin-top: 24px;">OK</p>'
        app.logger.info('PAYTOWALLET success')
    except Exception as e:
        msg = '<p style="margin-top: 24px;">NG</p>'
        app.logger.error('SHOWCLOSED failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return msg

def changehostname(value):
    try:
        app.logger.info('CHANGE_HOSTNAME start')

        cmd = "cp /etc/hosts /etc/hosts_tmp"
        linux_cmd_subprocess(cmd)

        cmd = "sudo sed -i '/127.0.1.1/d' /etc/hosts_tmp"
        linux_cmd_subprocess(cmd)

        value = value.strip()

        cmd = "sudo sed -i '$a 127.0.1.1 " + value + "' /etc/hosts_tmp"
        linux_cmd_subprocess(cmd)

        cmd = "sudo hostnamectl set-hostname " + value
        linux_cmd_subprocess(cmd)

        cmd = "cp /etc/hosts_tmp /etc/hosts"
        linux_cmd_subprocess(cmd)

        cmd = "rm -f /etc/hosts_tmp"
        linux_cmd_subprocess(cmd)

        app.logger.info(linux_cmd_subprocess('hostname'))
        app.logger.info('CHANGE_HOSTNAME success')
    except Exception as e:
        app.logger.error('CHANGE_HOSTNAME failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
        raise SubprocessError(cmd)
    return

def downloadlog():
    try:
        app.logger.info('DOWNLOADLOG start')
        os.chdir(PROGDIR)
        cmd = 'sudo rm -rf ' + PROGDIR + '/logfiles/'
        linux_cmd_subprocess(cmd)
        linux_cmd_subprocess('mkdir ' + PROGDIR + '/logfiles')

        #remove recently file
        cmd = 'sudo rm -f ' + PROGDIR + '/lnshield_log_*'
        linux_cmd_subprocess(cmd)

        os.chdir(PROGDIR + '/logfiles')
        linux_cmd_subprocess('mkdir ' + PROGDIR + '/logfiles/stdout')
        linux_cmd_subprocess('mkdir ' + PROGDIR + '/logfiles/mainnet')
        linux_cmd_subprocess('mkdir ' + PROGDIR + '/logfiles/testnet')
        linux_cmd_subprocess('mkdir ' + PROGDIR + '/logfiles/rpiweb')

        #~/Prog/logs
        cmd = 'cp -r ' + PROGDIR + '/logs/ ' + PROGDIR + '/logfiles/stdout'
        linux_cmd_subprocess(cmd)

        #~/Prog/ptarmigan/install/mainnet
        if os.path.exists(COPYNODEDIR + '/mainnet/logs'):
            cmd = 'cp -r ' + COPYNODEDIR + '/mainnet/logs/ ' + PROGDIR + '/logfiles/mainnet'
            linux_cmd_subprocess(cmd)

        #~/Prog/ptarmigan/install/mainnet
        if os.path.exists(COPYNODEDIR + '/testnet/logs'):
            cmd = 'cp -r ' + COPYNODEDIR + '/testnet/logs/ ' + PROGDIR + '/logfiles/testnet' 
            linux_cmd_subprocess(cmd)

        #~/Prog/rpi_web/logs
        cmd = 'cp -r ' + WEBDIR + '/logs/ ' + PROGDIR + '/logfiles/rpiweb'
        linux_cmd_subprocess(cmd)

        os.chdir(PROGDIR)
        date = "{0:%Y%m%d%H%M%S}".format(datetime.datetime.now()) + '.tar.gz'
        hostname = linux_cmd_subprocess('hostname').strip()
        filename = 'lnshield_log_' + hostname + '_' + date
        cmd = 'tar zcf ' + filename + ' -C ' + PROGDIR + ' logfiles'
        linux_cmd_subprocess(cmd)

        linux_cmd_subprocess('rm -rf ' + PROGDIR + '/logfiles')
        
        app.logger.info('DOWNLOADLOG success')
    except Exception as e:        
        app.logger.error('DOWNLOADLOG failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return filename

def changedigest(user, password):
    try:
        app.logger.info('CHANGE_DIGEST start')
        cmd = 'echo {\\"' + user + '\\":\\"' + password + '\\"} > ' + WEBDIR + '/static/digest.txt'
        app.logger.info(cmd)
        linux_cmd_subprocess(cmd)
        app.logger.info('CHANGE_DIGEST success')
    except Exception as e:
        app.logger.error('CHANGE_DIGEST failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return

def changeuserpasswd(password):
    try:
        app.logger.info('CHANGE_USERPASSWD start')
        cmd = 'echo "pi:' + password + '" | sudo chpasswd'
        linux_cmd_subprocess(cmd)
        app.logger.info('CHANGE_USERPASSWD success')
    except Exception as e:
        app.logger.error('CHANGE_USERPASSWD failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return

def resetchaindata():
    try:
        app.logger.info('RESET_CHAINDATA start')
        try:
            os.chdir(NODEDIR)
            linux_cmd_subprocess('sudo systemctl stop rpi_ptarm')
            sleep(1)
        except:
            app.logger.info('"ptarmd" has already stopped.')
        dirinfo = linux_cmd_subprocess('ls /boot')
        if 'RPI_MAINNET' in dirinfo:
            cmd = 'rm -f ' + NODEDIR + '/walletmain/ptarm_p2wpkh.spvchain'
            linux_cmd_subprocess(cmd)
            result = 'OK: Chaindata of Mainnet is deleted.'
        else:
            cmd = 'rm -f ' + NODEDIR + '/wallettest/ptarm_p2wpkh.spvchain'
            linux_cmd_subprocess(cmd)
            result = 'OK: Chaindata of Testnet is deleted.'
    except Exception as e:
        result = 'NG'
        app.logger.error('RESET_CHAINDATA failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return result

def epaperreload(value):
    try:
        app.logger.info('EPAPER_RELOAD start')
        if value == 'REBOOT':
            cmd = 'bash ' + PROGDIR + '/bin/epaper_led.sh ' + 'REBOOT'
            linux_cmd_subprocess(cmd)
        elif value == 'SHUTDOWN':
            cmd = 'bash ' + PROGDIR + '/bin/epaper_led.sh ' + 'SHUTDOWN'
            linux_cmd_subprocess(cmd)
        elif value == '':
            cmd = 'bash ' + PROGDIR + '/bin/epaper_led.sh ' + 'CLIENT'
            linux_cmd_subprocess(cmd)
        elif value == '':
            cmd = 'bash ' + PROGDIR + '/bin/epaper_led.sh ' + 'APMODE'
            linux_cmd_subprocess(cmd)
        app.logger.info('EPAPER_RELOAD success')
    except Exception as e:
        app.logger.error('EPAPER_RELOAD failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                          'img/favicon.ico',mimetype='image/vnd.microsoft.icon')

@app.route('/')
def index(): 
    app.logger.info('access INDEX')
    return render_template('index.html')

@app.route('/index.html')
def back():
    app.logger.info('redirect INDEX')
    return redirect(url_for('index'))

@app.route('/send_backupfile')
def sendbk():
    try:
        app.logger.info('SEND_BACKUP start')
        cmd = 'ls ' + PROGDIR + '/lnshield_backup_*'
        file = linux_cmd_subprocess(cmd)
        file = (file.strip())

        #initialize DB
        os.chdir(COPYNODEDIR + '/mainnet')
        cmd = 'sudo ls | grep -v "script" | xargs rm -rf'
        linux_cmd_subprocess(cmd)

        os.chdir(COPYNODEDIR + '/testnet')
        cmd = 'sudo ls | grep -v "script" | xargs rm -rf'
        linux_cmd_subprocess(cmd)

    except Exception as e:
        app.logger.error('SEND_BACKUP failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))
    return send_file(file, as_attachment = True)

@app.route('/upload', methods=['GET', 'POST'])
def uploadbk():
    try:
        app.logger.info('UPLOAD_BACKUP start')
        os.chdir(PROGDIR)
        cmd = 'sudo rm -f ' + PROGDIR + '/*.tar.gz'
        linux_cmd_subprocess(cmd)
        file = request.files['bkfile']
        file.save(file.filename)
        result = '<p>Upload complete.</p>' + '<p>Please update DB.</p>'
        result += '<a href="/restore"><button class="sendbutton">Update</button></a>'
        app.logger.info('UPLOAD_BACKUP success')
    except Exception as e:
        result = '<p>Upload failed</p>'
        app.logger.error('UPLOAD_BACKUP failed')
        app.logger.error('type:' + str(type(e)))
        app.logger.error('args:' + str(e.args))

    return render_template('list19.html', result = Markup(result))

@app.route('/restore')
def restorebk():
    result = restore()
    return render_template('list19.html', result = Markup(result))

@app.route('/list1.html', methods = ['GET', 'POST'])
def li1():
    try:
        app.logger.info('access GETINFO')
        if request.args.get('post') is None :
            msg = ''
        else:
            msg = request.args.get('post')
        
        result = callback_getinfo()
    except:
        result.append('NG')
    return render_template('list1.html', result = Markup(result[0]), msg = msg)

@app.route('/list2.html', methods = ['GET', 'POST'])
def li2():
    try:
        app.logger.info('access GETCHANNEL')
        if request.args.get('post') is None :
            msg = ''
        else:
            msg = request.args.get('post')

        result = []
        result = callback_getchannel()
        print(result)
        if result[0] == '<table class="u-full-width"><caption></caption><thead><tr class="headline"><th class="headtd">name</th><th>value</th></tr></thead><tbody>':
            result = list(result)
            result[0] = 'No Channels.'
            print(result)
        if request.method == 'POST': 
            cmdlist = request.form['idselect']
            idlist = result[1]
            cmdlist = cmdlist.split(' ')
            id = int(cmdlist[0])
            id = idlist[id]
            if cmdlist[1] == 'mutual':
                msg = callback_close_mutual(id)
            elif cmdlist[1] == 'force':
                msg = callback_close_force(id)
            return redirect(url_for('li2', result = Markup(result[0]), post = Markup(msg)))
    except:
        result.append('No Channels.')
    return render_template('list2.html', result = Markup(result[0]), msg = msg)

@app.route('/list3.html', methods = ['GET', 'POST'])
def li3():
    try:
        app.logger.info('access SHOWCLOSEDCHANNEL')
        result = []
        result = callback_closed_channel()
        if request.method == 'POST':
            try:
                num = request.form['idselect']
                num = int(num) - 1
                value = result[1]
                value = value[num]
                result = showclosed(value)
                return render_template('list3.html', result = Markup(result)) 
            except Exception as e:
                app.logger.error('SHOWCLOSEDCHANNEL failed')
                app.logger.error('type:' + str(type(e)))
                app.logger.error('args:' + str(e.args))    
    except:
        result.append('No Channels.')
    return render_template('list3.html', result = Markup(result[0]))
      
@app.route('/list4.html')
def li4():
    try:
        app.logger.info('access LISTINVOICE')
        result = callback_listinvoice()
        if result == '<table class="u-full-width"><caption></caption><thead><tr class="headline"><th class="headtd">name</th><th>value</th></tr></thead><tbody></tbody></table>':
            result = 'No Invoices.'
    except:
        result = 'NG'
    return render_template('list4.html', result = Markup(result))

@app.route('/list5.html', methods = ['GET', 'POST'])
def li5():
    try:
        app.logger.info('access CREATEINVOICE')
        if request.args.get('amount') is None :
            result = ''
        else:
            result = request.args.get('amount')
        if request.method == 'POST':
            invoice = request.form['invoice']
            image = callback_createinvoice(invoice)
            invoice = '{:,}'.format(int(invoice))
            result = 'OK: ' + invoice + ' msat requested.'
            result += image 
            return redirect(url_for('li5', amount=result))
    except:
        result = 'NG'
    return render_template('list5.html', result = Markup(result))

@app.route('/list6.html')
def li6():
    try:
        app.logger.info('access GET_1STLAYER_INFO')
        result = callback_get1stlayerinfo()
    except:
        result = 'NG'
    return render_template('list6.html', result = Markup(result))

@app.route('/list8.html', methods = ['GET', 'POST'])
def li8():
    try:
        app.logger.info('access EMPTYWALLET')
        if request.args.get('post') is None :
            result = ''
        else:
            result = request.args.get('post')
        if request.method == 'POST':
            addr = request.form['addr']
            result = callback_emptywallet(addr)
            return redirect(url_for('li8', post=result))
    except:
        result = 'NG'
    return render_template('list8.html', result = Markup(result))

@app.route('/list9.html', methods = ['GET', 'POST'])
def li9():
    try:
        app.logger.info('access CONNECT')
        if request.args.get('post') is None :
            result = ''
        else:
            result = request.args.get('post')
        if request.method == 'POST':
            info = request.form['nodeinfo']
            result = callback_connect(info)
            return redirect(url_for('li9', post=result))
    except:
        result = 'NG'
    return render_template('list9.html', result = Markup(result))

@app.route('/list12.html', methods = ['GET', 'POST'])
def li12():
    try:
        app.logger.info('access WiFi_SETTING')
        if request.args.get('post') is None :
            result = ''
        else:
            result = request.args.get('post')
        if request.method == 'POST':
            ssid = request.form['ssid']
            password = request.form['password']
            result = wpa_supplicant(ssid, password)
            return redirect(url_for('li12', post=result))
    except:
        result = 'NG'
    return render_template('list12.html', result = Markup(result))

@app.route('/list14.html', methods = ['GET', 'POST'])
def li14():
    app.logger.info('access REBOOT')
    if request.method == 'POST':
        cmdid = request.form['cmdselect']
        if cmdid == 'normal':
            app.logger.info('NORMAL REBOOT START')
            epaperreload("REBOOT")
            subprocess.Popen('sleep 5 && sudo reboot', stdout=subprocess.PIPE, shell=True, stderr=subprocess.STDOUT)
            return redirect('/index.html')
        elif cmdid == 'client':
            app.logger.info('CHANGE CLIENT MODE')
            client()
            epaperreload("CLIENT")
            subprocess.Popen('sleep 5 && sudo reboot', stdout=subprocess.PIPE, shell=True, stderr=subprocess.STDOUT)
            return redirect('/index.html')
        elif cmdid == 'ap':
            app.logger.info('CHANGE AP MODE')
            apmode()
            epaperreload("APMODE")
            subprocess.Popen('sleep 5 && sudo reboot', stdout=subprocess.PIPE, shell=True, stderr=subprocess.STDOUT)
            return redirect('/index.html')
    return render_template('list14.html')

@app.route('/list15.html', methods = ['GET', 'POST'])
def li15():
    try:
        app.logger.info('access SHUTDOWN')
        if request.method == 'POST':
            app.logger.info('SHUTDOWN START')
            epaperreload("SHUTDOWN")
            subprocess.Popen('sleep 5 && sudo shutdown', stdout=subprocess.PIPE, shell=True, stderr=subprocess.STDOUT)
            return redirect('/index.html')
    except:
        app.logger.error('NG')
    return render_template('list15.html')

@app.route('/list17.html')
def li17():
    try:
        app.logger.info('access DEVICEINFO')
        result = deviceinfo()
        ip = result[0]
        maxsize = result[1]
        usedsize = result[2]
        ssid = result[3]
        hn = result[4]
        user = result[5]
        ver_prog = result[6]
        ver_ptarm = result[7]
        ver_bin = result[8]
        ver_epaper = result[9]
        ver_uart = result[10]
        ver_web = result[11]
    except:
        app.logger.error('NG')
    return render_template('list17.html',\
                ip = ip,
                maxsize = maxsize,
                usedsize = usedsize,
                ssid = ssid,
                hostname = hn,
                id = user,
                ver_prog = ver_prog,
                ver_ptarm = ver_ptarm,
                ver_bin = ver_bin,
                ver_epaper = ver_epaper,
                ver_uart = ver_uart,
                ver_web = ver_web)

@app.route('/list18.html', methods = ['GET', 'POST'])
def li18():
    try:
        app.logger.info('access CHANGE_BLOCKCHAIN_NETWORK')
        msg = ''
        if request.method == 'POST':
            msg = blockchainnetworkchange()
            app.logger.info('NORMAL REBOOT START')
            epaperreload("REBOOT")
            subprocess.Popen('sleep 5 && sudo reboot', stdout=subprocess.PIPE, shell=True, stderr=subprocess.STDOUT)
            return redirect('/index.html')

        dirinfo = linux_cmd_subprocess('ls /boot')
        if 'RPI_MAINNET' in dirinfo:
            result = 'Now, this node connects MAINNET.'
            network = 'TESTNET'
        else:
            result = 'Now, this node connects TESTNET.'
            network = 'MAINNET'
    except:
        result = 'NG'
    return render_template('list18.html', result = result, msg = msg, network = network)

@app.route('/list19.html', methods = ['GET', 'POST'])
def li19():
    try:
        app.logger.info('access BACKUP/RESTORE')
        if request.args.get('post') is None :
            result = ''
        else:
            result = request.args.get('post')

        if request.method == 'POST':
            cmdid = request.form['idselect']
            if cmdid == 'bk':
                result = backup()
                return redirect(url_for('li19', post = Markup(result)))
            elif cmdid == 'rs':
                result = upload()
                return redirect(url_for('li19', post = Markup(result)))
    except:
        result = 'NG'
    
    response_body = render_template('list19.html', result = Markup(result))
    response = prepare_response(response_body)
    return response

@app.route('/list20.html', methods = ['GET', 'POST'])
def li20():
    try:
        app.logger.info('access PAYTOWALLET')
        if request.args.get('msg') is None :
            msg = ''
        else:
            msg = request.args.get('msg')
        
        result = paytowalletlist()
        if request.method == 'POST':
            msg = paytowallet()
            return redirect(url_for('li20', result = Markup(result), msg = Markup(msg)))
    except:
        result = 'NG'
    return render_template('list20.html', result = Markup(result), msg = Markup(msg))

@app.route('/list21.html', methods = ['GET', 'POST'])
def li21():
    try:
        app.logger.info('access CHANGE_HOSTNAME')
        if request.args.get('post') is None :
            result = ''
        else:
            result = request.args.get('post')

        if request.method == 'POST':
            hostname = request.form['hostname']
            changehostname(hostname)
            result = 'OK'
            return redirect(url_for('li21', post = Markup(result)))
    except:
        result = 'NG'
    return render_template('list21.html', result = Markup(result))

@app.route('/list22.html', methods = ['GET', 'POST'])
def li22():
    try:
        app.logger.info('access DOWNLOADLOG')
        result = ''
        if request.method == 'POST':
            filename = downloadlog()
            file = PROGDIR + '/' + filename
            return send_file(file, as_attachment = True)
    except:
        result = 'NG'
    return render_template('list22.html', result = Markup(result))

@app.route('/list23.html', methods = ['GET', 'POST'])
def li23():
    try:
        app.logger.info('access CHANGE_DIGEST')
        if request.args.get('post') is None :
            result = ''
        else:
            result = request.args.get('post')

        if request.method == 'POST':
            user = request.form['user']
            password = request.form['password']
            changedigest(user, password)
            result = 'OK'
    except:
        result = 'NG'
    return render_template('list23.html', result = Markup(result))

@app.route('/list24.html', methods = ['GET', 'POST'])
def li24():
    try:
        app.logger.info('access CHANGE_USERPASSWD')
        if request.args.get('post') is None :
            result = ''
        else:
            result = request.args.get('post')

        if request.method == 'POST':
            password = request.form['password']
            changeuserpasswd(password)
            result = 'OK'
            return redirect(url_for('li24', post = Markup(result)))
    except:
        result = 'NG'
    return render_template('list24.html', result = Markup(result))

@app.route('/list25.html', methods = ['GET', 'POST'])
def li25():
    try:
        app.logger.info('access RESET_CHAINDATA')
        result = ''
        if request.method == 'POST':
            result = resetchaindata()
            app.logger.info('NORMAL REBOOT START')
            epaperreload("REBOOT")
            subprocess.Popen('sleep 5 && sudo reboot', stdout=subprocess.PIPE, shell=True, stderr=subprocess.STDOUT)
            return redirect('/index.html')
    except:
        result = 'NG'
    return render_template('list25.html', result = Markup(result))

if __name__ == '__main__':
    if len(sys.argv) == 1:
        port = 80
    else:
        port = sys.argv[1]

    if len(sys.argv) <= 2:
        conf_path = '/home/pi/Prog/bin/rpi_config.ini'
    else:
        conf_path = sys.argv[2]

    config_init(conf_path)
    flask_init()
    app.logger.info('START RPI_WEB')
    app.logger.info('CONFIG=' + conf_path)
    serve(app, host='0.0.0.0', port=port)
