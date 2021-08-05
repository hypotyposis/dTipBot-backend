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

w3_arbitrum = Web3(Web3.HTTPProvider(config.ARBITRUM_ENDPOINT))
# print(w3_arbitrum.eth.get_transaction_count("config.DEFAULT_ACCOUNT"))

w3_matic = Web3(Web3.HTTPProvider(config.MATIC_ENDPOINT))
# print(w3_matic.eth.get_transaction_count("0x0c45bC2ef5b43823D644b0328133Da870701caE6"))

w3 = Web3(Web3.HTTPProvider(config.AURORA_ENDPOINT))
print(w3.eth.get_transaction_count("0x7654c7a2F26088317fAd978f375d197B5c51709c"))