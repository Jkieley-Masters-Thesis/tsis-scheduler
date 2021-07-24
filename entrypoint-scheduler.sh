#!/bin/bash

echo '127.0.0.1 jamesk-kubernetes-master' >>/etc/hosts
ssh -f -N asu-master
python3.8 main.py
