import asyncio
import json
import os
from web3 import Web3
from dotenv import load_dotenv
from colorama import init, Fore

# Initialize colorama
init(autoreset=True)

# Load environment variables
load_dotenv()

rpc_url = os.getenv("RPC_URL")
private_key = os.getenv("PRIVATE_KEY4")
usdc_address = os.getenv("USDC_ADDRESS")
lending_pool_proxy_address = os.getenv("LENDING_POOL_PROXY")

if not all([rpc_url, private_key, usdc_address, lending_pool_proxy_address]):
    raise ValueError("Missing one or more required environment variables.")

provider = Web3.HTTPProvider(rpc_url)
w3 = Web3(provider)

if not w3.is_connected():
    raise ConnectionError("Failed to connect to RPC")
else:
    print(Fore.GREEN + "✅ Connected to RPC successfully!")

wallet = w3.eth.account.from_key(private_key)

with open("abi_usdc.json") as f:
    usdc_abi = json.load(f)
with open("abi_lending.json") as f:
    lending_pool_proxy_abi = json.load(f)

usdc_contract = w3.eth.contract(address=usdc_address, abi=usdc_abi)
lending_pool_contract = w3.eth.contract(address=lending_pool_proxy_address, abi=lending_pool_proxy_abi)

GAS_PRICE = w3.to_wei(0.018, "gwei")  # 0.018 Gwei
AMOUNT = w3.to_wei(1001.1, "mwei")    # 1001.1 USDC (6 decimals)
ON_BEHALF_OF = wallet.address
REFERRAL_CODE = 0
TO = wallet.address

def log_transaction(tx_number, action, tx_hash, status, deposit_count=None, withdraw_count=None):
    status_color = Fore.GREEN if status == 1 else Fore.RED
    status_text = 'Success' if status == 1 else 'Failed'
    print(Fore.CYAN + "-" * 40)
    if deposit_count is not None:
        print(Fore.YELLOW + f"[TX {tx_number}] {action} #{deposit_count} - 1000 USDC")
    elif withdraw_count is not None:
        print(Fore.YELLOW + f"[TX {tx_number}] {action} #{withdraw_count} - 1000 USDC")
    else:
        print(Fore.YELLOW + f"[TX {tx_number}] {action} - 1000 USDC")
    print(Fore.WHITE + f"Hash    : {tx_hash}")
    print(status_color + f"Status  : {status_text}")
    print(Fore.CYAN + "-" * 40 + "\n")

def save_tx_count(deposit_counter, withdraw_counter, total_tx, deposit_count, withdraw_count):
    data = {
        "deposit_counter": deposit_counter,
        "withdraw_counter": withdraw_counter,
        "total_tx": total_tx,
        "deposit_count": deposit_count,
        "withdraw_count": withdraw_count
    }
    with open("transaction_status.json", "w") as f:
        json.dump(data, f)

def load_tx_count():
    if os.path.exists("transaction_status.json"):
        with open("transaction_status.json", "r") as f:
            return json.load(f)
    else:
        return {
            "deposit_counter": 0,
            "withdraw_counter": 0,
            "total_tx": 0,
            "deposit_count": 1,
            "withdraw_count": 1
        }

async def wait_until_confirmed(tx_hash, check_interval=5):
    print(Fore.MAGENTA + f"⏳ Waiting for confirmation of transaction {w3.to_hex(tx_hash)} ...")
    while True:
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if receipt is not None and receipt.status is not None:
                return receipt
        except:
            pass
        await asyncio.sleep(check_interval)

async def deposit_usdc(tx_number, deposit_counter, deposit_count, nonce):
    try:
        gas_estimate = lending_pool_contract.functions.deposit(
            usdc_address, AMOUNT, ON_BEHALF_OF, REFERRAL_CODE
        ).estimate_gas({'from': wallet.address})

        tx = lending_pool_contract.functions.deposit(
            usdc_address, AMOUNT, ON_BEHALF_OF, REFERRAL_CODE
        ).build_transaction({
            'from': wallet.address,
            'gas': int(gas_estimate * 1.2),
            'maxFeePerGas': GAS_PRICE,
            'maxPriorityFeePerGas': GAS_PRICE,
            'nonce': nonce,
        })

        signed_tx = wallet.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(Fore.BLUE + f"Waiting for confirmation of Deposit TX {tx_number}...")
        tx_receipt = await wait_until_confirmed(tx_hash)
        log_transaction(tx_number, "Deposit", w3.to_hex(tx_hash), tx_receipt.status, deposit_count=deposit_count)

        if tx_receipt.status == 1:
            deposit_counter += 1
        return deposit_counter, nonce + 1
    except Exception as e:
        print(Fore.RED + f"Deposit Error: {e}")
        return deposit_counter, nonce

async def withdraw_usdc(tx_number, withdraw_counter, withdraw_count, nonce):
    try:
        gas_estimate = lending_pool_contract.functions.withdraw(
            usdc_address, AMOUNT, TO
        ).estimate_gas({'from': wallet.address})

        tx = lending_pool_contract.functions.withdraw(
            usdc_address, AMOUNT, TO
        ).build_transaction({
            'from': wallet.address,
            'gas': int(gas_estimate * 1.2),
            'maxFeePerGas': GAS_PRICE,
            'maxPriorityFeePerGas': GAS_PRICE,
            'nonce': nonce,
        })

        signed_tx = wallet.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(Fore.BLUE + f"Waiting for confirmation of Withdraw TX {tx_number}...")
        tx_receipt = await wait_until_confirmed(tx_hash)
        log_transaction(tx_number, "Withdraw", w3.to_hex(tx_hash), tx_receipt.status, withdraw_count=withdraw_count)

        if tx_receipt.status == 1:
            withdraw_counter += 1
        return withdraw_counter, nonce + 1
    except Exception as e:
        print(Fore.RED + f"Withdraw Error: {e}")
        return withdraw_counter, nonce

async def main():
    print("🚀 Starting transaction loop...")
    tx_data = load_tx_count()

    deposit_counter = tx_data["deposit_counter"]
    withdraw_counter = tx_data["withdraw_counter"]
    total_tx = tx_data["total_tx"]
    deposit_count = tx_data["deposit_count"]
    withdraw_count = tx_data["withdraw_count"]

    nonce = w3.eth.get_transaction_count(wallet.address)

    while total_tx < 150:
        if total_tx % 2 == 0:
            deposit_counter, nonce = await deposit_usdc(total_tx + 1, deposit_counter, deposit_count, nonce)
            deposit_count += 1
        else:
            withdraw_counter, nonce = await withdraw_usdc(total_tx + 1, withdraw_counter, withdraw_count, nonce)
            withdraw_count += 1

        total_tx += 1
        save_tx_count(deposit_counter, withdraw_counter, total_tx, deposit_count, withdraw_count)

    if os.path.exists("transaction_status.json"):
        os.remove("transaction_status.json")
        print(Fore.RED + "🗑️ transaction_status.json deleted after 110 TXs.")

    print(Fore.GREEN + "✅ All 150 transactions completed!")

if __name__ == "__main__":
    asyncio.run(main())
