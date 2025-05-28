import asyncio
import json
import os
from web3 import Web3
from dotenv import load_dotenv
from colorama import init, Fore

# Init
init(autoreset=True)
load_dotenv()

# Env
rpc_url = os.getenv("RPC_URL")
private_key = os.getenv("PRIVATE_KEY4")
usdc_address = os.getenv("USDC_ADDRESS")
lending_pool_proxy_address = os.getenv("LENDING_POOL_PROXY")

# Validasi
if not all([rpc_url, private_key, usdc_address, lending_pool_proxy_address]):
    raise ValueError("Missing one or more required environment variables.")

# Web3
w3 = Web3(Web3.HTTPProvider(rpc_url))
if not w3.is_connected():
    raise ConnectionError("❌ Failed to connect to RPC")
print(Fore.GREEN + "✅ Connected to RPC")

# Wallet
wallet = w3.eth.account.from_key(private_key)

# ABI
with open("abi_usdc.json") as f:
    usdc_abi = json.load(f)
with open("abi_lending.json") as f:
    lending_abi = json.load(f)

# Contract
usdc = w3.eth.contract(address=usdc_address, abi=usdc_abi)
lending = w3.eth.contract(address=lending_pool_proxy_address, abi=lending_abi)

# Constants
GAS_PRICE = w3.to_wei(0.018, "gwei")
AMOUNT = w3.to_wei(1001.1, "mwei")  # 1001.1 USDC (6 decimals)
ON_BEHALF_OF = wallet.address
REFERRAL_CODE = 0
TO = wallet.address

# File JSON
STATUS_FILE = "transaction_status.json"

# Load Status
def load_tx_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE) as f:
            data = json.load(f)
            # pastikan key next_action ada, kalau tidak default ke deposit
            if "next_action" not in data:
                data["next_action"] = "deposit"
            return data
    return {
        "tx_index": 0,
        "nonce": w3.eth.get_transaction_count(wallet.address, 'pending'),
        "deposit_count": 1,
        "withdraw_count": 1,
        "next_action": "deposit"
    }

# Save Status
def save_tx_status(data):
    with open(STATUS_FILE, "w") as f:
        json.dump(data, f)

# Log
def log(tx_index, action, tx_hash, status, count):
    print(Fore.CYAN + "-" * 40)
    print(Fore.YELLOW + f"[TX {tx_index+1}] {action.capitalize()} #{count} - 1000 USDC")
    print(Fore.WHITE + f"Hash    : {tx_hash}")
    print((Fore.GREEN if status == 1 else Fore.RED) + f"Status  : {'Success' if status == 1 else 'Failed'}")
    print(Fore.CYAN + "-" * 40)

# Deposit
async def deposit(nonce, tx_index, count):
    try:
        gas_estimate = lending.functions.deposit(usdc_address, AMOUNT, ON_BEHALF_OF, REFERRAL_CODE).estimate_gas({'from': wallet.address})
        tx = lending.functions.deposit(usdc_address, AMOUNT, ON_BEHALF_OF, REFERRAL_CODE).build_transaction({
            'from': wallet.address,
            'nonce': nonce,
            'gas': int(gas_estimate * 1.2),
            'maxFeePerGas': GAS_PRICE,
            'maxPriorityFeePerGas': GAS_PRICE,
        })
        signed = wallet.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        log(tx_index, "deposit", w3.to_hex(tx_hash), receipt.status, count)
        return receipt.status
    except Exception as e:
        print(Fore.RED + f"Deposit Error: {e}")
        return 0

# Withdraw
async def withdraw(nonce, tx_index, count):
    try:
        gas_estimate = lending.functions.withdraw(usdc_address, AMOUNT, TO).estimate_gas({'from': wallet.address})
        tx = lending.functions.withdraw(usdc_address, AMOUNT, TO).build_transaction({
            'from': wallet.address,
            'nonce': nonce,
            'gas': int(gas_estimate * 1.2),
            'maxFeePerGas': GAS_PRICE,
            'maxPriorityFeePerGas': GAS_PRICE,
        })
        signed = wallet.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        log(tx_index, "withdraw", w3.to_hex(tx_hash), receipt.status, count)
        return receipt.status
    except Exception as e:
        print(Fore.RED + f"Withdraw Error: {e}")
        return 0

# Main
async def main():
    print(Fore.MAGENTA + "🚀 Starting 110 transactions...")
    data = load_tx_status()
    nonce = data["nonce"]
    tx_index = data["tx_index"]
    deposit_count = data["deposit_count"]
    withdraw_count = data["withdraw_count"]
    action = data.get("next_action", "deposit")

    while tx_index < 110:
        if action == "deposit":
            status = await deposit(nonce, tx_index, deposit_count)
            if status:
                deposit_count += 1
                action = "withdraw"
                nonce += 1
                tx_index += 1
            else:
                print(Fore.YELLOW + "Deposit gagal, coba Withdraw...")
                status_wd = await withdraw(nonce, tx_index, withdraw_count)
                if status_wd:
                    withdraw_count += 1
                    action = "deposit"
                    nonce += 1
                    tx_index += 1
                else:
                    print(Fore.RED + "Withdraw juga gagal, ulangi transaksi yang sama.")
                    # ulangi tanpa increment
        else:
            status = await withdraw(nonce, tx_index, withdraw_count)
            if status:
                withdraw_count += 1
                action = "deposit"
                nonce += 1
                tx_index += 1
            else:
                print(Fore.YELLOW + "Withdraw gagal, coba Deposit...")
                status_dp = await deposit(nonce, tx_index, deposit_count)
                if status_dp:
                    deposit_count += 1
                    action = "withdraw"
                    nonce += 1
                    tx_index += 1
                else:
                    print(Fore.RED + "Deposit juga gagal, ulangi transaksi yang sama.")
                    # ulangi tanpa increment

        # Simpan status hanya kalau berhasil transaksi
        save_tx_status({
            "tx_index": tx_index,
            "nonce": nonce,
            "deposit_count": deposit_count,
            "withdraw_count": withdraw_count,
            "next_action": action
        })

    # Hapus file jika sudah selesai
    if os.path.exists(STATUS_FILE):
        os.remove(STATUS_FILE)
        print(Fore.RED + "🗑️ transaction_status.json deleted after 110 TXs.")

    print(Fore.GREEN + "✅ Semua transaksi selesai!")

# Run
asyncio.run(main())
