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
nonce_state = redis.StrictRedis(host='localhost', port=6379, db=4, decode_responses=True)
nonce_state_matic = redis.StrictRedis(host='localhost', port=6379, db=6, decode_responses=True)
nonce_state_arbitrum = redis.StrictRedis(host='localhost', port=6379, db=7, decode_responses=True)

w3 = Web3(Web3.HTTPProvider(config.AURORA_ENDPOINT))
with open('./ERC20.abi', 'r') as f:
    ERC20_abi = f.read()
contract_instance =  w3.eth.contract(address=config.AURORA_BOT_TOKEN, abi=ERC20_abi)

#get the balance of ABT tokens of certain address
def get_ABTbalance_of(user_id):
    # print(user_id, type(user_id))
    private_key = redis_client.get(str(user_id))
    address = Account.from_key(private_key).address
    balance = contract_instance.functions.balanceOf(address).call()
    print("balance: ", balance, type(balance))
    return balance/math.pow(10, 18)

time.sleep(10)

for user_id in redis_client.keys():
    print(user_id, type(user_id))
    private_key = redis_client.get(user_id)
    print(private_key)
    address = Account.from_key(private_key).address
    print(address)
    nonce = w3.eth.get_transaction_count(address)
    nonce_state.set(int(user_id), nonce)
    # nonce_state_matic.set(int(user_id), 0)
    # nonce_state_arbitrum.set(int(user_id), 0)

# print(Account.from_key("0x1f86727342299b3cbfa4b47f32d8b35456b7782c2c70938005fc7afbd0cb4b49").address)

# for user_id in nonce_state.keys():
#     print(user_id)
#     nonce = nonce_state.get(user_id)
#     print(nonce)