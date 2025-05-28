import json
import asyncio
from web3 import Web3
from eth_account import Account
from eth_account.signers.local import LocalAccount
from dotenv import load_dotenv
import os

load_dotenv()

web3 = Web3(Web3.HTTPProvider(os.getenv("RPC")))
CHAIN_ID = int(os.getenv("CHAIN_ID"))

with open("abi.json") as f:
    ABI = json.load(f)

TOKEN_ADDRESS = Web3.to_checksum_address(os.getenv("TOKEN"))
LENDING_ADDRESS = Web3.to_checksum_address(os.getenv("LENDING"))

USDC_DECIMALS = 6
AMOUNT = int(float(os.getenv("AMOUNT")) * (10 ** USDC_DECIMALS))

with open("wallets.json") as f:
    WALLETS = json.load(f)

def build_tx(account: LocalAccount, to, data):
    return {
        'from': account.address,
        'to': to,
        'data': data,
        'nonce': web3.eth.get_transaction_count(account.address),
        'gas': 150000,
        'gasPrice': web3.eth.gas_price,
        'chainId': CHAIN_ID
    }

async def try_deposit_then_withdraw(account, lending, token):
    try:
        tx_data = lending.encodeABI(fn_name="deposit", args=[TOKEN_ADDRESS, AMOUNT])
        tx = build_tx(account, LENDING_ADDRESS, tx_data)
        signed_tx = account.sign_transaction(tx)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status == 1:
            print(f"✅ Deposit Success: {account.address}")
            return "deposit"
        else:
            raise Exception("Deposit failed")
    except Exception as e:
        print(f"Deposit Error: {e}")
        try:
            tx_data = lending.encodeABI(fn_name="withdraw", args=[TOKEN_ADDRESS, AMOUNT])
            tx = build_tx(account, LENDING_ADDRESS, tx_data)
            signed_tx = account.sign_transaction(tx)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt.status == 1:
                print(f"✅ Withdraw Success (after deposit fail): {account.address}")
                return "withdraw"
            else:
                raise Exception("Withdraw after deposit fail also failed")
        except Exception as e:
            print(f"Withdraw Error: {e}")
            return None

async def try_withdraw_then_deposit(account, lending, token):
    try:
        tx_data = lending.encodeABI(fn_name="withdraw", args=[TOKEN_ADDRESS, AMOUNT])
        tx = build_tx(account, LENDING_ADDRESS, tx_data)
        signed_tx = account.sign_transaction(tx)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status == 1:
            print(f"✅ Withdraw Success: {account.address}")
            return "withdraw"
        else:
            raise Exception("Withdraw failed")
    except Exception as e:
        print(f"Withdraw Error: {e}")
        try:
            tx_data = lending.encodeABI(fn_name="deposit", args=[TOKEN_ADDRESS, AMOUNT])
            tx = build_tx(account, LENDING_ADDRESS, tx_data)
            signed_tx = account.sign_transaction(tx)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt.status == 1:
                print(f"✅ Deposit Success (after withdraw fail): {account.address}")
                return "deposit"
            else:
                raise Exception("Deposit after withdraw fail also failed")
        except Exception as e:
            print(f"Deposit Error: {e}")
            return None

async def main():
    for entry in WALLETS:
        key = entry["key"]
        mode = entry["mode"]
        account = Account.from_key(key)
        lending = web3.eth.contract(address=LENDING_ADDRESS, abi=ABI)

        status = None
        if mode == "deposit":
            status = await try_deposit_then_withdraw(account, lending, TOKEN_ADDRESS)
        else:
            status = await try_withdraw_then_deposit(account, lending, TOKEN_ADDRESS)

        if status:
            entry["mode"] = "withdraw" if status == "deposit" else "deposit"

    with open("wallets.json", "w") as f:
        json.dump(WALLETS, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
