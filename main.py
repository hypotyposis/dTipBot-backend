import json
from flask import Flask, request, Response
from pprint import pprint
from eth_account import Account
import redis
from web3 import Web3, exceptions
import os
import math
import config, private_config
import telegram
import qrcode
import re
import time

app = Flask(__name__)
app.config.from_object(config)

bot = telegram.Bot(token=private_config.TELEGRAM_BOT_TOKEN)

# REDIS_URL = "redis://:password@localhost:6379/0"
# redis_client = FlaskRedis(app)
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
state_manager = redis.StrictRedis(host='localhost', port=6379, db=1, decode_responses=True)
transfer_queue = redis.StrictRedis(host='localhost', port=6379, db=2, decode_responses=True)
multi_transfer_state = redis.StrictRedis(host='localhost', port=6379, db=3, decode_responses=True)
nonce_state = redis.StrictRedis(host='localhost', port=6379, db=4, decode_responses=True)
user_current_network = redis.StrictRedis(host='localhost', port=6379, db=5, decode_responses=True)
nonce_state_matic = redis.StrictRedis(host='localhost', port=6379, db=6, decode_responses=True)
nonce_state_arbitrum = redis.StrictRedis(host='localhost', port=6379, db=7, decode_responses=True)

chain_nonce_state_manager = {
    "Aurora": nonce_state,
    "Matic": nonce_state_matic,
    "Arbitrum": nonce_state_arbitrum
}

chain_id_dict = {
    "Aurora": 1313161555,
    "Matic": 80001,
    "Arbitrum": 421611
}

w3 = Web3(Web3.HTTPProvider(config.AURORA_ENDPOINT))
w3_matic = Web3(Web3.HTTPProvider(config.MATIC_ENDPOINT))
w3_arbitrum = Web3(Web3.HTTPProvider(config.ARBITRUM_ENDPOINT))

chain_w3_client_dict = {
    "Aurora": w3,
    "Matic": w3_matic,
    "Arbitrum": w3_arbitrum
}

w3_kovan = Web3(Web3.HTTPProvider('https://kovan.infura.io/v3/5147c36db83c48f88f770376bfb3622b'))
price_feed_abi = '[{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"description","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint80","name":"_roundId","type":"uint80"}],"name":"getRoundData","outputs":[{"internalType":"uint80","name":"roundId","type":"uint80"},{"internalType":"int256","name":"answer","type":"int256"},{"internalType":"uint256","name":"startedAt","type":"uint256"},{"internalType":"uint256","name":"updatedAt","type":"uint256"},{"internalType":"uint80","name":"answeredInRound","type":"uint80"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"latestRoundData","outputs":[{"internalType":"uint80","name":"roundId","type":"uint80"},{"internalType":"int256","name":"answer","type":"int256"},{"internalType":"uint256","name":"startedAt","type":"uint256"},{"internalType":"uint256","name":"updatedAt","type":"uint256"},{"internalType":"uint80","name":"answeredInRound","type":"uint80"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"version","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]'
price_feed_address = '0x9326BFA02ADD2366b30bacB125260Af641031331'
price_feed_contract = w3_kovan.eth.contract(address=price_feed_address, abi=price_feed_abi)
with open('./ERC20.abi', 'r') as f:
    ERC20_abi = f.read()
with open('./Proxy.abi', 'r') as f:
    Prxoy_abi = f.read()
contract_instance =  w3.eth.contract(address=config.AURORA_BOT_TOKEN, abi=ERC20_abi)
proxy_contract = w3.eth.contract(address=config.PROXY_ADDRESS, abi=Prxoy_abi)

def get_ETHbalance_of(user_id):
    # return 10
    private_key = redis_client.get(str(user_id))
    address = Account.from_key(private_key).address
    # balance = contract_instance.functions.balanceOf(address).call()
    chain = user_current_network.get(str(user_id))
    print("chain: ", chain)
    w3_client = chain_w3_client_dict[chain]
    balance = w3_client.eth.get_balance(address)
    print("balance: ", balance, type(balance))
    return balance/math.pow(10, 18)

#transfer ETH
def transfer_ETH(user_id, to_address, amount, nonce):
    chain = user_current_network.get(str(user_id))
    print("chain: ", chain)
    chain_id = int(chain_id_dict[chain])
    amount = int(amount * math.pow(10,18))
    print("transfer amount: ", amount)
    private_key = redis_client.get(str(user_id))
    from_address = Account.from_key(private_key).address
    print("from address: ", from_address)
    tx_options = {
        'to': to_address,
        'value': amount,
        'gas': w3.toHex(3000000),
        'gasPrice': w3.toWei(3, 'gwei'),
        'nonce': nonce,
        'chainId': chain_id,
    }
    print(tx_options)
    chain = user_current_network.get(str(user_id))
    print("chain: ", chain)
    w3_client = chain_w3_client_dict[chain]
    # tx = contract_instance.functions.transfer(to_address, amount).buildTransaction(tx_options)
    signed_tx = w3_client.eth.account.sign_transaction(tx_options, private_key)
    try:
        result = w3_client.eth.send_raw_transaction(signed_tx.rawTransaction)
        w3_client.eth.waitForTransactionReceipt(result)
        print('result: ', result, type(result), result.hex())
        nonce_state_manager = chain_nonce_state_manager[chain]
        nonce_state_manager.set(user_id, int(nonce_state_manager.get(str(user_id)))+1)
        return w3_client.toHex(result)
    except exceptions.SolidityError as error:
        print('SolidityError: ', error)
        return "Error"
    except ValueError as error:
        print('ValueError: ', error)
        return "Error"

#approve to Proxy Contract
def approve_ABT(user_id, amount):
    amount = int(amount * math.pow(10,18))
    print("approve amount: ", amount)
    private_key = redis_client.get(str(user_id))
    from_address = Account.from_key(private_key).address
    tx_options = {
        'gas': w3.toHex(3000000),
        'gasPrice': w3.toWei(3, 'gwei'),
        'nonce': w3.eth.get_transaction_count(from_address),
        'chainId': 1313161555,
    }
    print(tx_options)
    tx = contract_instance.functions.approve(config.PROXY_ADDRESS, amount).buildTransaction(tx_options)
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    try:
        result = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        w3.eth.waitForTransactionReceipt(result)
        print('result: ', result, type(result), result.hex())
        return w3.toHex(result)
    except exceptions.SolidityError as error:
        print('SolidityError: ', error)
        return "Error"
    except ValueError as error:
        print('ValueError: ', error)
        return "Error"

#deposit ABT token to Proxy by transferFrom
def deposit_ABT_to_proxy(user_id, amount):
    amount = int(amount * math.pow(10,18))
    print("deposit amount: ", amount)
    private_key = redis_client.get(str(user_id))
    from_address = Account.from_key(private_key).address
    tx_options = {
        'gas': w3.toHex(3000000),
        'gasPrice': w3.toWei(3, 'gwei'),
        'nonce': w3.eth.get_transaction_count(from_address),
        'chainId': 1313161555,
    }
    print(tx_options)
    tx = proxy_contract.functions.deposit(from_address, amount).buildTransaction(tx_options)
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    try:
        result = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        w3.eth.waitForTransactionReceipt(result)
        print('result: ', result, type(result), result.hex())
        return w3.toHex(result)
    except exceptions.SolidityError as error:
        print('SolidityError: ', error)
        return "Error"
    except ValueError as error:
        print('ValueError: ', error)
        return "Error"

#withdraw ABT from proxy
def withdraw_ABT_from_proxy(from_user_id, to_address, amount):
    amount = int(amount * math.pow(10,18))
    print("withdraw amount: ", amount)
    private_key = redis_client.get(str(from_user_id))
    from_address = Account.from_key(private_key).address
    tx_options = {
        'gas': w3.toHex(3000000),
        'gasPrice': w3.toWei(3, 'gwei'),
        'nonce': w3.eth.get_transaction_count(config.DEFAULT_ACCOUNT),
        'chainId': 1313161555,
    }
    print(tx_options)
    tx = proxy_contract.functions.withdraw(from_address, to_address, amount).buildTransaction(tx_options)
    signed_tx = w3.eth.account.sign_transaction(tx, private_config.SECRET_KEY)
    try:
        result = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        w3.eth.waitForTransactionReceipt(result)
        print('result: ', result, type(result), result.hex())
        return w3.toHex(result)
    except exceptions.SolidityError as error:
        print('SolidityError: ', error)
        return "Error"
    except ValueError as error:
        print('ValueError: ', error)
        return "Error"

#transfer ABT token user_id: int to_address: string, amount: string
def transfer_ABT(user_id, to_address, amount, nonce):
    amount = int(amount * math.pow(10,18))
    print("transfer amount: ", amount)
    private_key = redis_client.get(str(user_id))
    from_address = Account.from_key(private_key).address
    print("from address: ", from_address)
    tx_options = {
        'gas': w3.toHex(3000000),
        'gasPrice': w3.toWei(3, 'gwei'),
        'nonce': nonce,
        'chainId': 1313161555,
    }
    print(tx_options)
    tx = contract_instance.functions.transfer(to_address, amount).buildTransaction(tx_options)
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    try:
        result = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        w3.eth.waitForTransactionReceipt(result)
        print('result: ', result, type(result), result.hex())
        nonce_state_manager = chain_nonce_state_manager[chain]
        nonce_state_manager.set(user_id, int(nonce_state_manager.get(str(user_id)))+1)
        # nonce_state.set(user_id, int(nonce_state.get(str(user_id)))+1)
        return w3.toHex(result)
    except exceptions.SolidityError as error:
        print('SolidityError: ', error)
        return "Error"
    except ValueError as error:
        print('ValueError: ', error)
        return "Error"

#check if the input is valid for a transfer amount
#input is a string check if it can be tranfer to float
def is_amount_valid(s):
    return True
    collection = ['0','1','2','3','4','5','6','7','8','9','.', ' ']
    for letter in s:
        if letter not in collection:
            return False
    if re.match(config.AMOUNT_REGEX_PATTERN, s) == None:
        return False
    if s[0] == '.' or s[-1] == ['.']:
        return False
    if s.count('.', 0, len(s)) > 1:
        return False
    return True

#generate QR Code of the user's public address
def get_deposit_info(user_id):
    private_key = redis_client.get(str(user_id))
    address = Account.from_key(private_key).address
    qrcode_img = qrcode.make(address)
    #写入文件
    with open(str(user_id) + '.png', 'wb') as f:
        qrcode_img.save(f)
    return address

#get the balance of ABT tokens of certain address
def get_ABTbalance_of(user_id):
    # print(user_id, type(user_id))
    private_key = redis_client.get(str(user_id))
    address = Account.from_key(private_key).address
    balance = contract_instance.functions.balanceOf(address).call()
    print("balance: ", balance, type(balance))
    return balance/math.pow(10, 18)

# init user's account by sending each 100 ABT tokens
def init_account(private_key):
    address = Account.from_key(private_key).address
    # print(address, type(address))
    amount = int(100 * math.pow(10, 18))
    print("init amount: ", amount)
    # name = contract_instance.functions.name().call()
    # print(name)
    tx_options = {
        'gas': w3.toHex(3000000),
        'gasPrice': w3.toWei(3, 'gwei'),
        'nonce': w3.eth.get_transaction_count(config.DEFAULT_ACCOUNT),
        'chainId': 1313161555,
    }
    print(tx_options)
    tx = contract_instance.functions.transfer(address, amount).buildTransaction(tx_options)
    signed_tx = w3.eth.account.sign_transaction(tx, private_config.SECRET_KEY)
    try:
        result = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        w3.eth.waitForTransactionReceipt(result)
        print('result: ', result, type(result), result.hex())
    except exceptions.SolidityError as error:
        print('SolidityError: ', error)
    except ValueError as error:
        print('ValueError: ', error)

@app.route('/', methods=['POST'])
def onmessage():
    # print(request.form)
    # print(request.data)
    # print(request.method)
    # print(request.values)
    # print(request.headers)
    # print(request.args)

    try:
        message_data = json.loads(request.data)

        #message is inline query
        if 'inline_query' in message_data:
            print(message_data)
            update_id = message_data['update_id']
            inline_query = message_data['inline_query']
            inline_query_id = inline_query['id']
            from_info = inline_query['from']
            user_id = from_info['id']
            first_name = from_info['first_name']
            if 'last_name' in from_info:
                last_name = " " + from_info['last_name']
            else:
                last_name = ""
            # last_name = from_info['last_name'] or ' '
            # chat_type = inline_query['chat_type']
            query = inline_query['query']
            # print("query: ", query, type(query))
            offset = inline_query['offset']
            keyboard = [
                [
                    telegram.InlineKeyboardButton("💰💰 Snatch! 💰💰", callback_data = inline_query_id + "|" + query + "|" + str(user_id), pay=True),
                ]
            ]
            reply_markup = telegram.InlineKeyboardMarkup(keyboard)
            # contact = telegram.InlineQueryResultContact(
            #     type="contact",
            #     id="1",
            #     phone_number="+86 181 1511 16016",
            #     first_name="付",
            #     reply_markup=reply_markup
            # )
            number = "1"
            amount = "0"
            query_list = query.split()
            if len(query_list) == 1:
                number = str(1)
                amount = query_list[0]
            elif len(query_list) == 2:
                number = query_list[1]
                amount = query_list[0]
            chain = user_current_network.get(str(user_id))
            if chain == "Matic":
                chain = "Polygon"
            input_message_content = telegram.InputTextMessageContent(
                message_text = first_name + last_name + " is sending you " + number + " red envelope, total " + amount + " ETH " + "on " + chain + "." + "\nCheck your balance at\nhttps://t.me/dtipbot/."
            )
            article = telegram.InlineQueryResultArticle(
                id="2",
                title="💰 Send " + amount + " ETH. " + number + " red envelope." ,
                input_message_content=input_message_content,
                reply_markup=reply_markup
            )
            input_message_content_value_error = telegram.InputTextMessageContent(
                message_text = "The input amount is not valid!"
            )
            article_value_error = telegram.InlineQueryResultArticle(
                id="3",
                title="The input amount is not valid!",
                input_message_content=input_message_content_value_error
            )

            if is_amount_valid(query) == False: #amount valid check before record into the transfer_queue
                results = [article_value_error]
                bot.answer_inline_query(inline_query_id=inline_query_id, results=results, cache_time=0)
                return "Invalid amount input"
            else:
                results = [article]
                bot.answer_inline_query(inline_query_id=inline_query_id, results=results, cache_time=0)
                return "Valid input"
                # pending_transfer = json.dumps({'sender': user_id, 'amount': query})
                # transfer_queue.set(inline_query_id, pending_transfer)

                return "Inline query received."

        #receive inlineKeyBoardButton callback
        if 'callback_query' in message_data:
            print(message_data)
            update_id = message_data['update_id']
            callback_query = message_data['callback_query']
            callback_query_id = callback_query['id']
            inline_message_id = callback_query['inline_message_id']
            print("inline_message_id: ", inline_message_id)
            from_info = callback_query['from']
            user_id = from_info['id']
            first_name = from_info['first_name']
            if 'last_name' in from_info:
                last_name = " " + from_info['last_name']
            else:
                last_name = ''
            # last_name = from_info['last_name'] or ' '
            user_name = first_name + last_name
            user_name = first_name
            inline_message_id = callback_query['inline_message_id']
            chat_instance = callback_query['chat_instance']
            data = callback_query['data']
            print("callback_data: ", data)
            data = data.split("|")
            inline_query_id = data[0]
            print("inline_query_id: ", inline_query_id)
            amount_number = data[1].split()      
            sender = int(data[2])
            if len(amount_number) == 1:
                amount = float(amount_number[0])
                if user_id == sender:
                    return "invalid clicker"
                    # if inline_message_id not in transfer_queue.keys():
                    #     transfer_queue.set(inline_message_id, "sender" + " " + str(sender) + " " + "confirmed" )
                    #     # approve_ABT(sender, amount)
                    #     # time.sleep(8)
                    #     # deposit_ABT_to_proxy(sender, amount)
                    #     # bot.answer_callback_query(callback_query_id=callback_query_id, text="Sender confirmed.")
                    #     return "sender confirmed"
                    # if inline_message_id in transfer_queue.keys():
                    #     state = transfer_queue.get(inline_message_id)
                    #     state = state.split()
                    #     if state[0] == "receiver":
                    #         receiver = state[1]
                    #         if str(receiver) not in redis_client.keys():
                    #             print("new user: ", receiver)
                    #             a = Account.create()
                    #             private_key = w3.toHex(a.key)
                    #             init_account(private_key)
                    #             redis_client.set(receiver, private_key)
                    #         private_key = redis_client.get(str(receiver))
                    #         to_address = Account.from_key(private_key).address
                    #         transfer_ABT(sender, to_address, amount)
                    #         transfer_queue.set(inline_message_id, "transfer done")
                    #         return "transfer established"
                    #     if state == "transfer done":
                    #         bot.answer_callback_query(callback_query_id=callback_query_id, text="Transfer has accomplished.")
                    #         return "transfer accomplished"
                    #     if state == "sender" + " " + str(sender) + " " + "confirmed":
                    #         # bot.answer_callback_query(callback_query_id=callback_query_id, text="Sender has confirmed.")
                    #         return "sender has confirmed"
                    #     # else:
                    #     #     state = state.split()
                    #     #     if state[0] == "receiver":
                    #     #         receiver = int(state[1])
                    #     #         if str(receiver) not in redis_client.keys():
                    #     #             print("new user: ", receiver)
                    #     #             a = Account.create()
                    #     #             private_key = w3.toHex(a.key)
                    #     #             init_account(private_key)
                    #     #             redis_client.set(receiver, private_key)
                    #     #         private_key = redis_client.get(str(receiver))
                    #     #         to_address = Account.from_key(private_key).address
                    #     #         time.sleep(8)
                    #     #         transfer_ABT(sender, to_address, amount)
                    #     #         transfer_queue.set(inline_message_id, "transfer done")
                    #     #         # bot.answer_callback_query(callback_query_id=callback_query_id, text="Transfer established.")
                    #     #         return "transfer established"
                    #         # else:
                    #         #     # bot.answer_callback_query(callback_query_id=callback_query_id, text="Transfer has corrupted.")
                    #         #     return "error"
                if user_id != sender: #it must be receiver
                    if inline_message_id in transfer_queue.keys() and transfer_queue.get(inline_message_id) == "done":
                        bot.answer_callback_query(callback_query_id=callback_query_id, text="Transfer has accomplished.")
                        return "transfer accomplished."
                    if str(user_id) not in redis_client.keys():
                        print("new user: ", user_id)
                        a = Account.create()
                        private_key = w3.toHex(a.key)
                        # init_account(private_key)

                        redis_client.set(user_id, private_key)
                        user_current_network.set(user_id, "Aurora")
                        # nonce_state.set(user_id, 0)
                        chain = user_current_network.get(str(user_id))
                        print("chain: ", chain)
                        nonce_state_manager = chain_nonce_state_manager[chain]
                        nonce_state_manager.set(user_id, 0)
                    
                    receiver = user_id
                    receiver_private_key = redis_client.get(str(receiver))
                    to_address = Account.from_key(receiver_private_key).address
                    print(receiver, receiver_private_key, to_address)
                    bot.answer_callback_query(callback_query_id=callback_query_id, text="You have accepted the transfer.")
                    chain = user_current_network.get(str(sender))
                    print("chain: ", chain)
                    nonce_state_manager = chain_nonce_state_manager[chain]
                    nonce = int(nonce_state_manager.get(str(sender)))
                    # transfer_ABT(sender, to_address, amount, nonce)
                    transfer_ETH(sender, to_address, amount, nonce)
                    transfer_queue.set(inline_message_id, "done")
                    return "transfer established."


                # if inline_message_id not in transfer_queue.keys():
                #     transfer_queue.set(inline_message_id, "receiver" + " " + str(user_id) + " " + "confirmed")
                #     # bot.answer_callback_query(callback_query_id=callback_query_id, text="Receiver confirmed.")
                #     return "receiver confirmed"
                # elif inline_message_id in transfer_queue.keys():
                #     if transfer_queue.get(inline_message_id) == "transfer done":
                #         bot.answer_callback_query(callback_query_id=callback_query_id, text="Transfer has accomplished.")
                #         return "transfer accomplished"
                #     if transfer_queue.get(inline_message_id) == "receiver" + " " + str(user_id) + " " + "confirmed":
                #         # bot.answer_callback_query(callback_query_id=callback_query_id, text="Receiver has confirmed.")
                #         return "receiver has confirmed"
                #     elif transfer_queue.get(inline_message_id) == "sender" + " " + str(sender) + " " + "confirmed":
                #         receiver_private_key = redis_client.get(user_id)
                #         to_address = Account.from_key(receiver_private_key).address
                #         transfer_ABT(sender, to_address, amount)
                #         # time.sleep(8)
                #         # withdraw_ABT_from_proxy(sender, to_address, amount)
                #         # bot.answer_callback_query(callback_query_id=callback_query_id, text="Transfer established.")
                #         return "transfer established"
                #     else:
                #         # bot.answer_callback_query(callback_query_id=callback_query_id, text="Transfer has corrupted.")
                #         return "error"
            elif len(amount_number) == 2:
                amount = float(amount_number[0])
                number  = int(amount_number[1])
                if user_id == sender:
                    return "invalid clicker"
                if user_id != sender:
                    receiver = user_id
                    if str(receiver) not in redis_client.keys():
                        print("new user: ", user_id)
                        a = Account.create()
                        private_key = w3.toHex(a.key)
                        # init_account(private_key)
                        redis_client.set(receiver, private_key)
                        user_current_network.set(user_id, "Aurora")
                        # nonce_state.set(receiver, 0)
                        chain = user_current_network.get(str(user_id))
                        print("chain: ", chain)
                        nonce_state_manager = chain_nonce_state_manager[chain]
                        nonce_state_manager.set(user_id, 0)
                    if inline_message_id not in multi_transfer_state.keys():
                        print("first claim")
                        accepters = str(receiver)
                        multi_transfer_state.set(inline_message_id, accepters)
                        receiver_private_key = redis_client.get(str(receiver))
                        to_address = Account.from_key(receiver_private_key).address
                        divided_amount = int(amount * math.pow(10, 18))//number/math.pow(10, 18)
                        bot.answer_callback_query(callback_query_id=callback_query_id, text=user_name + " has claimed the first reward.")
                        chain = user_current_network.get(str(sender))
                        print("chain: ", chain)
                        nonce_state_manager = chain_nonce_state_manager[chain]
                        nonce = int(nonce_state_manager.get(str(sender)))
                        # transfer_ABT(sender, to_address, divided_amount, nonce)
                        transfer_ETH(sender, to_address, divided_amount, nonce)
                        return "first claim"
                    
                    if inline_message_id in multi_transfer_state.keys():
                        print("****accept****")
                        accepters = multi_transfer_state.get(inline_message_id)
                        accepters_list = accepters.split()
                        if len(accepters_list) >= number:
                            print("full")
                            return "full"
                        if len(accepters_list) < number:
                            accepters = accepters + " " + str(receiver)
                        multi_transfer_state.set(inline_message_id, accepters)
                        receiver_private_key = redis_client.get(str(receiver))
                        to_address = Account.from_key(receiver_private_key).address
                        divided_amount = int(amount * math.pow(10, 18))//number/math.pow(10, 18)
                        bot.answer_callback_query(callback_query_id=callback_query_id, text=user_name + " have accepted the transfer.")
                        chain = user_current_network.get(str(sender))
                        print("chain: ", chain)
                        nonce_state_manager = chain_nonce_state_manager[chain]
                        nonce = int(nonce_state_manager.get(str(sender)))
                        # transfer_ABT(sender, to_address, divided_amount, nonce)
                        transfer_ETH(sender, to_address, divided_amount, nonce)
                        return "****claim****"

                return "Red envelope snatched"

                    
            # if inline_query_id in transfer_queue.keys() == False:
            #     bot.answer_callback_query(callback_query_id=callback_query_id, text="Nonexistent transfer request!")
            #     return "Nonexistent transfer request"
            # else:
            #     #matched. Do the transfer
            #     pending_transfer = json.loads(transfer_queue.get(inline_query_id))
            #     # print(pending_transfer)
            #     sender = int(pending_transfer['sender'])
            #     amount = float(pending_transfer['amount'])
            #     #generate a new address if the accepter has not logged in
            #     if accepter not in redis_client.keys():
            #         a = Account.create()
            #         private_key = w3.toHex(a.key)
            #         init_account(private_key)
            #         redis_client.set(accepter, private_key)
                
            #     accepter_private_key = redis_client.get(accepter)
            #     to_address = Account.from_key(accepter_private_key).address


            #     transfer_queue.delete(inline_query_id)
            #     bot.answer_callback_query(callback_query_id=callback_query_id, text="Transfer established.")
            #     return "Transfer established"

            return "callback query received."



        # print(json.loads(request.data))
        message = request.json['message']
        print(message, type(message))
        chat_id = message['chat']['id']
        # print(chat_id, type(chat_id))
        message_id = message['message_id']

        # chat = bot.get_chat(chat_id=chat_id)
        # print("chat: ", chat)

        # print(redis_client.get("foo"))
        # print(redis_client.keys())
        keys = redis_client.keys()
        # print(keys, type(keys))
        from_info = message['from']
        if (from_info['is_bot'] == False and (str(from_info['id']) in keys) == False):
            user_id = from_info['id']
            # print(user_id)
            print("new user: ", user_id)
            a = Account.create()
            # print('address: ', a.address)
            # pprint(a.key)  # HexBytes 内的是私钥  pprint可以打印出来 
            private_key = w3.toHex(a.key)
            # print('key: ', private_key, type(private_key))
            # print('from key: ', Account.from_key(private_key).address)
            # init_account(private_key)
            redis_client.set(user_id, private_key)
            user_current_network.set(user_id, "Aurora")
            # nonce_state.set(user_id, 0)
            chain = user_current_network.get(str(user_id))
            print("chain: ", chain)
            nonce_state_manager = chain_nonce_state_manager[chain]
            nonce_state_manager.set(user_id, 0)

        # print(config.SECRET_KEY)
        # name = contract_instance.functions.name().call()
        # print(name)
        user_id = from_info['id']
        current_network = user_current_network.get(str(user_id))
        if current_network == "Matic":
            current_network = "Polygon"
        if (message['text'] == '/start' and message['entities'][0]['type'] == 'bot_command'):
            bot.send_message(text='dTipBot\n/start - ❤️Know the usage of this bot!\n/network - 🥳Choose your network!\n/balance - ☘️Check the balance of your current account!\n/deposit - 🤑Funding your account!\n/withdraw - 💰Withdraw from your current account!' + '\nCurrent Chain: ' + current_network,
                        chat_id=chat_id, reply_to_message_id=message_id)
        elif (message['text'] == '/help' and message['entities'][0]['type'] == 'bot_command'):
            bot.send_message(text='dTipBot\n/start - ❤️Know the usage of this bot!\n/network - 🥳Choose your network!\n/balance - ☘️Check the balance of your current account!\n/deposit - 🤑Funding your account!\n/withdraw - 💰Withdraw from your current account!' + '\nCurrent Chain: ' + current_network,
                                chat_id=chat_id, reply_to_message_id=message_id)
        elif message['text'] == '/network' and message['entities'][0]['type'] == 'bot_command':
            keyboard = [
                [
                    telegram.KeyboardButton(text="Aurora"),
                    telegram.KeyboardButton(text="Polygon"),
                    telegram.KeyboardButton(text="Arbitrum")
                ]
            ]
            reply_markup = telegram.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)
            bot.send_message(text='Current Chain: ' + current_network + '\n' + "choose your network", chat_id=chat_id, reply_markup=reply_markup)
        elif message['text'] == 'Aurora':
            user_id = message['from']['id']
            user_current_network.set(user_id, "Aurora")
            bot.send_message(text='Set your network to Aurora', chat_id=chat_id, reply_to_message_id=message_id)
        elif message['text'] == 'Polygon':
            user_id = message['from']['id']
            user_current_network.set(user_id, "Matic")
            bot.send_message(text='Set your network to Polygon', chat_id=chat_id, reply_to_message_id=message_id)
        elif message['text'] == 'Arbitrum':
            user_id = message['from']['id']
            user_current_network.set(user_id, "Arbitrum")
            bot.send_message(text='Set your network to Arbitrum', chat_id=chat_id, reply_to_message_id=message_id)
        elif (message['text'] == '/balance' and message['entities'][0]['type'] == 'bot_command'):
            user_id = message['from']['id']
            if message['from']['is_bot'] == False:
                # balance = get_ABTbalance_of(user_id)
                balance = get_ETHbalance_of(user_id)
                latestRoundData = price_feed_contract.functions.latestRoundData().call()
                price = int(latestRoundData[1])//math.pow(10,6)/100
                total_price = int(price * balance * 100)/100
            bot.send_message(text='Current Chain: ' + current_network + '\n' + 'Your ETH balance is %f.'%(balance) + "\n ≈ " + str(total_price) + " USD" + "\n_Powered by chainlink_", chat_id=chat_id, reply_to_message_id=message_id, parse_mode=telegram.ParseMode.MARKDOWN)
        elif (message['text'] == '/deposit' and message['entities'][0]['type'] == 'bot_command'):
            user_id = message['from']['id']
            if message['from']['is_bot'] == False:
                # bot.send_message(text='Generating Your QR Code...', chat_id=chat_id, reply_to_message_id=message_id)
                bot.send_chat_action(chat_id=chat_id, action="upload_photo")
                address = get_deposit_info(user_id)
                bot.send_message(text='The wallet address of your dTipBot is here👇👇👇.', chat_id=chat_id)
                bot.send_message(text=address, chat_id=chat_id)
                bot.send_photo(chat_id=chat_id, photo=open(str(user_id)+'.png', 'rb'))
        elif (message['text'] == '/withdraw' and message['entities'][0]['type'] == 'bot_command'):
            user_id = message['from']['id']
            if message['from']['is_bot'] == False:
                bot.send_message(text='Current Chain: ' + current_network + '\n' + 'OK. Send me the target address you wonna withdraw to.', chat_id=chat_id, reply_to_message_id=message_id)
                state_manager.set(user_id, "waiting for address")
        #receive the target address
        elif (len(message['text']) == 42 and message['text'][:2] == '0x' and state_manager.get(str(message['from']['id'])) and state_manager.get(str(message['from']['id'])) == "waiting for address"):
            user_id = message['from']['id']
            address = message['text']
            if message['from']['is_bot'] == False:
                bot.send_message(text='OK. Send me the amount of ETH you wonna withdraw. Your input should be in format like 20, 1.0 or all.', chat_id=chat_id, reply_to_message_id=message_id)
                state_manager.set(user_id, "waiting for amount with address " + address)
        elif (is_amount_valid(message['text']) == True or message['text'] == 'all') and state_manager.get(str(message['from']['id'])) and state_manager.get(str(message['from']['id']))[:18] == "waiting for amount":
            parsed_state = state_manager.get(str(message['from']['id'])).split()
            # print(parsed_state)
            user_id = message['from']['id']
            to_address = parsed_state[-1]
            if message['text'] == 'all':
                # amount = get_ABTbalance_of(user_id)
                balance = get_ETHbalance_of(user_id)
            else:
                amount = float(message['text'])
            if message['from']['is_bot'] == False:
                # if get_ABTbalance_of(user_id) < amount:
                if get_ETHbalance_of(user_id) < amount:
                    bot.send_message(text='Your aurora bot balance is not enough!', chat_id=chat_id, reply_to_message_id=message_id)
                    return "Your aurora bot balance is not enough!"
                chain = user_current_network.get(str(user_id))
                nonce_state_manager = chain_nonce_state_manager[chain]
                nonce = int(nonce_state_manager.get(str(user_id)))
                # tx_hash = transfer_ABT(user_id, to_address, amount, nonce)
                tx_hash = transfer_ETH(user_id, to_address, amount, nonce)
                bot.send_message(text='Yeah! 🎉🎉🎉Withdraw Success! The transaction hash is ' + tx_hash, chat_id=chat_id)
                state_manager.delete(str(user_id))
        else:
            bot.send_message(text='Message received but I cannot understand. Oh! What a shame!', chat_id=chat_id, reply_to_message_id=message_id)
        return json.dumps({'chat_id': chat_id, 'text': "Message Received."})
        # return "Received"
    except:
        return("An exception occurred")
# @app.route('/', methods=['GET'])
# def default():
#     print(request.form)
#     print(request.data)
#     print(request.method)
#     # print(request.values)
#     print(request.headers)
#     print(request.args)
#     return "Hello!"