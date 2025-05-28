import asyncio
import json
import os
from web3 import Web3
from dotenv import load_dotenv
from colorama import init, Fore
import time

# Initialize colorama
init(autoreset=True)

# Load environment variables
load_dotenv()

# Load from environment
rpc_url = os.getenv("RPC_URL")
private_key = os.getenv("PRIVATE_KEY4")
usdc_address = os.getenv("USDC_ADDRESS")
lending_pool_proxy_address = os.getenv("LENDING_POOL_PROXY")

# Check essential variables
if not all([rpc_url, private_key, usdc_address, lending_pool_proxy_address]):
    raise ValueError("Missing one or more required environment variables.")

# Configure RPC
provider = Web3.HTTPProvider(rpc_url)
w3 = Web3(provider)

# Check RPC connection
if w3.is_connected():
    print(Fore.GREEN + "✅ Connected to RPC successfully!")
else:
    raise ConnectionError("❌ Failed to connect to RPC")

# Load wallet
wallet = w3.eth.account.from_key(private_key)

# Load ABI files
with open("abi_usdc.json") as f:
    usdc_abi = json.load(f)

with open("abi_lending.json") as f:
    lending_pool_proxy_abi = json.load(f)

# Contract instances
usdc_contract = w3.eth.contract(address=usdc_address, abi=usdc_abi)
lending_pool_contract = w3.eth.contract(address=lending_pool_proxy_address, abi=lending_pool_proxy_abi)

# Transaction parameters
GAS_PRICE = w3.to_wei(0.018, "gwei")  # 0.018 Gwei
AMOUNT = w3.to_wei(1001.1, "mwei")    # 1000 USDC (6 decimals)
ON_BEHALF_OF = wallet.address
REFERRAL_CODE = 0
TO = wallet.address

# Transaction logger
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

# Save transaction counters
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

# Load previous transaction counters
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

# Deposit function
async def deposit_usdc(tx_number, deposit_counter, deposit_count):
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
            'nonce': w3.eth.get_transaction_count(wallet.address),
        })

        signed_tx = wallet.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        log_transaction(tx_number, "Deposit", w3.to_hex(tx_hash), tx_receipt.status, deposit_count=deposit_count)

        if tx_receipt.status == 1:
            deposit_counter += 1
        return deposit_counter
    except Exception as e:
        print(f"Deposit Error: {e}")
        return deposit_counter

# Withdraw function
async def withdraw_usdc(tx_number, withdraw_counter, withdraw_count):
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
            'nonce': w3.eth.get_transaction_count(wallet.address),
        })

        signed_tx = wallet.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        log_transaction(tx_number, "Withdraw", w3.to_hex(tx_hash), tx_receipt.status, withdraw_count=withdraw_count)

        if tx_receipt.status == 1:
            withdraw_counter += 1
        return withdraw_counter
    except Exception as e:
        print(f"Withdraw Error: {e}")
        return withdraw_counter

# Main function
async def main():
    print("🚀 Starting transaction loop...")
    tx_data = load_tx_count()

    deposit_counter = tx_data["deposit_counter"]
    withdraw_counter = tx_data["withdraw_counter"]
    total_tx = tx_data["total_tx"]
    deposit_count = tx_data["deposit_count"]
    withdraw_count = tx_data["withdraw_count"]

    for i in range(total_tx, 111):
        if i % 2 == 0:
            deposit_counter = await deposit_usdc(i + 1, deposit_counter, deposit_count)
            deposit_count += 1
        else:
            withdraw_counter = await withdraw_usdc(i + 1, withdraw_counter, withdraw_count)
            withdraw_count += 1

        total_tx += 1
        save_tx_count(deposit_counter, withdraw_counter, total_tx, deposit_count, withdraw_count)

        # If 110th transaction was withdraw, add 1 extra deposit
        if total_tx == 111 and total_tx % 2 != 0:
            print(Fore.RED + "⚠️ TX #110 was Withdraw. Adding extra Deposit...")
            deposit_counter = await deposit_usdc(total_tx + 1, deposit_counter, deposit_count)
            deposit_count += 1
            total_tx += 1
            save_tx_count(deposit_counter, withdraw_counter, total_tx, deposit_count, withdraw_count)

        # Remove status file when done
        if total_tx >= 111:
            os.remove("transaction_status.json")
            print(Fore.RED + "🗑️ transaction_status.json deleted after 111 TXs.")

    print(Fore.GREEN + "✅ All transactions completed!")

# Run the main function
asyncio.run(main())
