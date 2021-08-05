import json
from flask import Flask, request, Response
from pprint import pprint
from eth_account import Account
import redis
from web3 import Web3, exceptions
import os
import math
import config
import telegram
import qrcode
import re
import time

redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
user_current_network = redis.StrictRedis(host='localhost', port=6379, db=5, decode_responses=True)

for user_id in redis_client.keys():
    user_current_network.set(int(user_id), "Aurora")
    