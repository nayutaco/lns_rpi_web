#!/bin/bash
set -eu
wpa_passphrase "$1" "$2"
if [ $? == 0 ]; then
	wpa_passphrase "$1" "$2" >> /etc/wpa_supplicant/wpa_supplicant.conf
fi

