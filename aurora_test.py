from re import A
from web3 import Web3
from web3 import exceptions
import json
import config
import math
from eth_account import Account

w3 = Web3(Web3.HTTPProvider('https://testnet.aurora.dev/'))
print(w3.isConnected())

with open('./ERC20.abi', 'r') as f:
    abi = f.read()
    # abi = json.loads(abi)
    # print(abi, type(abi))
contract_instance =  w3.eth.contract(address=config.AURORA_BOT_TOKEN, abi=abi)
name = contract_instance.functions.name().call()
print(name)
defaultAccount = '0xc7BC8404fE99f6aCE8a4954B7d6D1e23B25afB08'
privateKey = '0x' + "36a0177516f51399faaaaa432a8e1e6525855a673a15b374ad46b5a76e666369"
# print(w3.eth.get_transaction_count("0x0c45bC2ef5b43823D644b0328133Da870701caE6"))

def approve_ABT(amount, nonce):
    amount = int(amount * math.pow(10,18))
    print("approve amount: ", amount)
    # private_key = redis_client.get(str(user_id))
    private_key = config.SECRET_KEY
    from_address = Account.from_key(private_key).address
    tx_options = {
        'gas': w3.toHex(3000000),
        'gasPrice': w3.toWei(3, 'gwei'),
        'nonce': w3.eth.get_transaction_count("0x2EF3594D01749f249c87391d5De5D27A7034eD53"),
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

nonce = w3.eth.get_transaction_count("0x2EF3594D01749f249c87391d5De5D27A7034eD53", "pending")
print(nonce, type(nonce))
approve_ABT(10, nonce)
# for i in range(5):
#     approve_ABT(10, nonce + i)
# approve_ABT(10, 1000)
# transaction_options = {
#     # 'to': tokenA_address,
#     # 'value': 1000000000,
#     'gas': w3.toHex(3000000),
#     'gasPrice': w3.toWei(3, 'gwei'),
#     'nonce': w3.eth.get_transaction_count(defaultAccount),
#     'chainId': 1313161555,
#     # 'data': contract_instance.functions.transfer('0x59bECb268753d8Db13c7Bb25C3A8AE2F03b2955D', 10000000000000)
# }
# toAddress = '0x59bECb268753d8Db13c7Bb25C3A8AE2F03b2955D'
# value = 100000000000000000 
# transaction = contract_instance.functions.transfer(toAddress, value).buildTransaction(transaction_options)
# print(transaction)
# signed_transaction = w3.eth.account.sign_transaction(transaction, privateKey)
# res = w3.eth.send_raw_transaction(signed_transaction.rawTransaction) 
# print(w3.toHex(res))

# swapContractAddress = '0xC7121D130764c515fBD424A9184427d6432Fe0fC'
# with open('./router.abi', 'r') as f:
#     router_abi = f.read()
# swap_contract = w3.eth.contract(address=swapContractAddress, abi=router_abi)
# factory = swap_contract.functions.factory().call()
# print(factory)
# tx_options = {
#     'gas': w3.toHex(3000000),
#     'gasPrice': w3.toWei(3, 'gwei'),
#     'nonce': w3.eth.get_transaction_count(defaultAccount),
#     'chainId': 1313161555,
# }
# tokenA = "0x28E7055d958e84dEA484427A9789D1F1dcB9b817"
# tokenB = "0x876255c7770Ee53B3005cD83e1be63351471560D"
# amountADesired = 1000000000000000000
# amountBDesired = 1000000000000000000
# amountAMin = 99000000000000000
# amountBMin = 99000000000000000
# toAddress = "0xc7BC8404fE99f6aCE8a4954B7d6D1e23B25afB08"
# deadline = 1645694546633878189
# tx = swap_contract.functions.addLiquidity(tokenA, tokenB, amountADesired, amountBDesired, amountAMin, amountBMin, toAddress, deadline).buildTransaction(tx_options)
# # print(tx)
# signed_tx = w3.eth.account.sign_transaction(tx, privateKey)
# # print(signed_tx.rawTransaction.hex())
# try:
#     result = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
#     w3.eth.waitForTransactionReceipt(result)
#     print('result: ', result, type(result), result.hex())
# except exceptions.SolidityError as error:
#     print('SolidityError: ', error)
# except ValueError as error:
#     print('ValueError: ', error)


# def test_factory_contract():
#     factory_contract_address = "0xd620bc3ebc5a1aC1053570d245C4857C55431119"
#     with open('./factory.abi', 'r') as f:
#         factory_abi = f.read()
#     factory_contract = w3.eth.contract(address=factory_contract_address, abi=factory_abi)
#     feeToSetter = factory_contract.functions.feeToSetter().call()
#     print('feeToSetter: ', feeToSetter)
#     token0 = "0x28E7055d958e84dEA484427A9789D1F1dcB9b817"
#     token1 = "0x876255c7770Ee53B3005cD83e1be63351471560D"
#     pair = factory_contract.functions.getPair(token0, token1).call()
#     print('pair: ', pair)
#     allPairs = factory_contract.functions.allPairs(0).call()
#     print('allPairs: ', allPairs)
#     transaction_options = {
#         'gas': w3.toHex(3000000),
#         'gasPrice': w3.toWei(3, 'gwei'),
#         'nonce': w3.eth.get_transaction_count(defaultAccount),
#         'chainId': 1313161555,
#     }
#     # transaction = factory_contract.functions.createPair(token0, token1).buildTransaction(transaction_options)
#     transaction = factory_contract.functions.setFeeTo(defaultAccount).buildTransaction(transaction_options)
#     print("transaction: ", transaction)
#     signed_transaction = w3.eth.account.sign_transaction(transaction, privateKey)
#     try:
#         result = w3.eth.send_raw_transaction(signed_transaction.rawTransaction)
#         w3.eth.waitForTransactionReceipt(result)
#         print('result: ', result, type(result), result.hex())
#     except exceptions.SolidityError as error:
#         print('SolidityError: ', error)
#     except ValueError as error:
#         print('ValueError: ', error)

# test_factory_contract()
# print(w3.toText(0x636f776dc3b6))
# print(w3.eth.get_block('latest'))
# print(w3.toText(0x000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000245472616e7366657248656c7065723a205452414e534645525f46524f4d5f4641494c454400000000000000000000000000000000000000000000000000000000))
# print(w3.toText(0x000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000245472616e7366657248656c7065723a205452414e534645525f46524f4d5f4641494c454400000000000000000000000000000000000000000000000000000000))
# print(w3.toText(0x000000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000018556e69737761705632526f757465723a20455850495245440000000000000000))