# from pprint import pprint
# from eth_account import Account
# from web3 import Web3
# from web3 import exceptions
# from PIL import Image

# # w3 = Web3(Web3.HTTPProvider('https://testnet.aurora.dev/'))
# # address = Account.from_key("0x80c1bb04ceed7fb835bbcd57df329d720922105a37b1b64b19f0ab18d89aedbd").addressSECRET_KEY = '0x' + "36a0177516f51399faaaaa432a8e1e6525855a673a15b374ad46b5a76e666369"
# address = "0xc7BC8404fE99f6aCE8a4954B7d6D1e23B25afB08"
# print(len(address))
# print(address[:2])

import re
pattern = '^(?!\(.*[^)]$|[^(].*\)$)\(?\$?(0|[1-9]\d{0,2}(,?\d{3})?)(\.\d\d?)?\)?$'
s = '1.342'
print(re.match(pattern, s))
collection = ['0','1','2','3','4','5','6','7','8','9','.']
print(collection)