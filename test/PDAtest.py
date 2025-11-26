#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
voltr_vault_inspect.py

用途：
- 從 Solana RPC 讀取 Voltr vault 的基礎鏈上資料（idle USDC、LP supply、持有 LP 等）
- 透過 Voltr 官方 API 取得「真實可提領金額」(userAssetAmount)
- 提供一些 debug helper，方便你之後擴充到其他 vault / 錢包

這支程式不是後端 API，只是「資料調查 / 資料源」的腳本。
你可以先用這支確認邏輯，之後再包成 FastAPI / Flask endpoint。
"""

import requests
from typing import Any, Dict, List, Optional

# ==============================
# 基本設定：Solana RPC & Voltr API
# ==============================

# Solana RPC endpoint
RPC = "https://api.mainnet-beta.solana.com"

# Voltr 公開 API base URL
VOLTR_API_BASE = "https://api.voltr.xyz"

# ==============================
# Vault / User 參數（你目前這個 vault）
# ==============================

# 這個 vault 的主帳戶（同時也是 state PDA）
VAULT_PUBKEY = "FajosXiYhqUDZ9cEB3pwS8n8pvcAbL3KzCGZnWDNvgLa"

# Vault 對應的 LP Mint
VAULT_LP_MINT = "A5dvM5NKnuo6tmwoiEFC22qcXcUsa6mUoUtpkxjm1gKg"

# Vault 持有 idle USDC 的 SPL Token Account
VAULT_IDLE_USDC_ATA = "3AK6wAysksFRke6KJasnnL1sFn73jqhwDNquR2WhgrhE"

# Solana 上 USDC 的 Mint（標準那顆）
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# 你的錢包（Signer / User）
USER_WALLET = "51pijqibmHQ17GZWjV8g8AyFWx1ZMmkUDtFR4Vz8Ah3F"

# 你自己的 LP token account（用來讀你持有多少 LP）
USER_LP_ATA = "BKCANLpd7r1k1dkki4Wj48kJZXd7CFFEzNnZXQGTrMk1"


# ==============================
# 通用：Solana RPC Helper
# ==============================

def rpc(method: str, params: List[Any]) -> Dict[str, Any]:
    """
    呼叫 Solana JSON-RPC 的共用 helper。

    method: RPC 方法名稱，例如 "getAccountInfo"
    params: 該方法對應的參數陣列

    回傳：完整 JSON dict，如：
      {
        "jsonrpc": "2.0",
        "result": {...},
        "id": 1
      }

    若 RPC 回傳 error，會丟 RuntimeError。
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }
    r = requests.post(RPC, json=payload)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data


def get_account_info(address: str, encoding: str = "base64") -> Optional[Dict[str, Any]]:
    """
    讀取任意帳戶的 AccountInfo。

    address: 要查的帳戶地址。
    encoding:
      - "base64"  ：適合 raw bytes，常見在自訂 PDA 狀態
      - "jsonParsed"：適合 SPL Token / Mint 等已知類型

    回傳：value 欄位（dict），或 None（找不到帳戶）
    """
    resp = rpc("getAccountInfo", [address, {"encoding": encoding}])
    return resp.get("result", {}).get("value")


# ==============================
# 通用：SPL Token 相關 Helper
# ==============================

def get_token_balance(token_account: str) -> float:
    """
    取得某個 SPL Token Account 的餘額（uiAmount，已處理 decimals）。

    token_account: SPL Token Account 地址（不是錢包，是 ATA）

    回傳：float，例如 1.234567 USDC
    """
    resp = rpc("getTokenAccountBalance", [token_account])
    value = resp.get("result", {}).get("value")
    if not value:
        return 0.0
    return float(value.get("uiAmount", 0.0))


def get_token_supply(mint: str) -> float:
    """
    取得某個 SPL Token Mint 的總供給（uiAmount）。

    mint: mint address

    回傳：float，例如 LP 總供給 9_037_456.396002
    """
    resp = rpc("getTokenSupply", [mint])
    value = resp.get("result", {}).get("value")
    if not value:
        return 0.0
    return float(value.get("uiAmount", 0.0))


def get_token_accounts_by_owner(owner: str) -> List[Dict[str, Any]]:
    """
    透過 getTokenAccountsByOwner 找出指定「token owner」底下所有 SPL Token Account。

    注意：
    - 這裡的 owner 是「token account 裡的 info.owner」，代表誰持有 token，
      不是 AccountInfo 的 owner 欄位（那個是 program id）。

    回傳：每個元素為：
      {
        "pubkey": "...",
        "account": {
          "data": {
            "program": "spl-token",
            "parsed": {
              "info": { "mint": "...", "owner": "...", "tokenAmount": {...} },
              "type": "account"
            },
            ...
          },
          ...
        }
      }
    """
    resp = rpc(
        "getTokenAccountsByOwner",
        [
            owner,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},  # SPL Token Program
            {"encoding": "jsonParsed"},
        ],
    )
    return resp.get("result", {}).get("value", [])


# ==============================
# Vault：鏈上 idle 資訊（只看 USDC）
# ==============================

def get_vault_idle_usdc() -> float:
    """
    取得 Vault idle USDC 數量。

    這裡直接讀 Vault 指定的 idle USDC ATA，
    也就是 vault 目前「現金部位」的大小。
    """
    return get_token_balance(VAULT_IDLE_USDC_ATA)


def get_vault_nav_idle_only() -> float:
    """
    只用 idle USDC 估算 Vault NAV。

    真實世界：
    - Vault 會把絕大部分資產放到外部協議（借貸 / LP / perp）
    - 所以真正 NAV 遠大於 idle USDC

    這個函式只是給你一個「鏈上可見現金部位」的數字，
    用來做 sanity check / 風險視角（例如 idle ratio）。
    """
    return get_vault_idle_usdc()


def get_user_lp_amount(user_lp_ata: str) -> float:
    """
    取得「使用者 LP Token Account」中的 LP 數量。
    """
    return get_token_balance(user_lp_ata)


def get_lp_price_and_share_idle_only(user_lp_ata: str) -> Dict[str, float]:
    """
    用「idle-only NAV」計算：
      - vault_nav_idle  : 只看 idle 的 NAV
      - lp_supply       : LP 總供給
      - user_lp         : 使用者持有 LP
      - lp_price_idle   : idle NAV / LP supply（只是理論價格）
      - share_idle      : 使用者 share（user_lp / lp_supply）

    注意：
    - 這個 LP 價格不會等於前端顯示的 NAV 價格，
      因為它沒有把外部倉位（外部協議）算進來。
    """
    vault_nav_idle = get_vault_nav_idle_only()
    lp_supply = get_token_supply(VAULT_LP_MINT)
    user_lp = get_user_lp_amount(user_lp_ata)

    if lp_supply <= 0:
        return {
            "vault_nav_idle": vault_nav_idle,
            "lp_supply": lp_supply,
            "user_lp": user_lp,
            "lp_price_idle": 0.0,
            "share_idle": 0.0,
        }

    lp_price_idle = vault_nav_idle / lp_supply
    share_idle = user_lp / lp_supply

    return {
        "vault_nav_idle": vault_nav_idle,
        "lp_supply": lp_supply,
        "user_lp": user_lp,
        "lp_price_idle": lp_price_idle,
        "share_idle": share_idle,
    }


def get_user_withdrawable_idle_only(user_lp_ata: str) -> Dict[str, float]:
    """
    根據 idle-only NAV 計算「理論 withdrawable（只看現金）」。

    這個值通常遠小於 Voltr 前端顯示的 withdrawable，
    因為沒有把外部倉位算進來，只能當作一種「下限 / sanity check」。
    """
    base = get_lp_price_and_share_idle_only(user_lp_ata)

    vault_nav_idle = base["vault_nav_idle"]
    lp_supply = base["lp_supply"]
    user_lp = base["user_lp"]
    lp_price_idle = base["lp_price_idle"]
    share_idle = base["share_idle"]

    withdrawable_idle = user_lp * lp_price_idle
    idle_usdc = get_vault_idle_usdc()
    idle_ratio = (idle_usdc / vault_nav_idle) if vault_nav_idle > 0 else 0.0

    return {
        "vault_nav_idle": vault_nav_idle,
        "lp_supply": lp_supply,
        "user_lp": user_lp,
        "lp_price_idle": lp_price_idle,
        "share_idle": share_idle,
        "withdrawable_idle": withdrawable_idle,
        "idle_usdc": idle_usdc,
        "idle_ratio": idle_ratio,
    }


# ==============================
# Vault：Token Authority / Token Accounts 調查
# ==============================

def get_vault_token_authority() -> str:
    """
    從 idle USDC ATA 中讀出「真正的 token owner」（Vault Token Authority）。

    - idle USDC ATA 的 AccountInfo（jsonParsed）裡，會有：

      data.parsed.info.owner = 某個 PDA / address

    - 這個 owner 才是「實際持有 vault 所有 token」的主體，
      我們可以用它去掃出 vault 目前有哪些 token accounts。
    """
    info = get_account_info(VAULT_IDLE_USDC_ATA, encoding="jsonParsed")
    if not info:
        raise RuntimeError("Idle USDC ATA not found on-chain.")

    parsed = info["data"]["parsed"]
    owner = parsed["info"]["owner"]
    return owner


def list_vault_token_accounts_by_authority() -> None:
    """
    Debug / 調查用：

    1. 從 idle USDC ATA 找到 token authority（Vault token owner）
    2. 用 getTokenAccountsByOwner 列出該 owner 名下所有 SPL Token Account

    這可以幫你確認：
    - vault 除了 idle USDC 之外，有沒有其它 token
    - 若有，可能是外部倉位的 share / reward token
    """
    authority = get_vault_token_authority()
    accounts = get_token_accounts_by_owner(authority)

    print(f"\n=== Vault Token Accounts (token owner = {authority}) ===")
    if not accounts:
        print("No SPL token accounts found for this authority.")
        return

    for i, acc in enumerate(accounts):
        pubkey = acc.get("pubkey")
        data = acc.get("account", {}).get("data", {})
        parsed = data.get("parsed", {})
        info = parsed.get("info", {})
        mint = info.get("mint")
        token_amount = info.get("tokenAmount", {})
        ui_amount = token_amount.get("uiAmount")
        decimals = token_amount.get("decimals")

        print(f"[{i}] {pubkey}")
        print(f"     mint:   {mint}")
        print(f"     amount: {ui_amount} (decimals={decimals})")


# ==============================
# Voltr API：真正的 NAV / User Withdrawable
# ==============================

def get_voltr_user_balance_raw(vault_pubkey: str, user_pubkey: str) -> Dict[str, Any]:
    """
    呼叫 Voltr 官方 API：
      GET /vault/{vault}/user/{user}/balance

    回傳完整 JSON，用來 debug / 觀察欄位。
    """
    url = f"{VOLTR_API_BASE}/vault/{vault_pubkey}/user/{user_pubkey}/balance"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    return data


def get_voltr_user_withdrawable_usdc(vault_pubkey: str, user_pubkey: str) -> float:
    """
    從 Voltr API 取得「真實可提領 USDC 數量」（含外部倉位 NAV）。

    API 回傳格式（你實測到的是）：
      {
        "success": True,
        "data": {
          "userAssetAmount": 2015964293
        }
      }

    其中：
      - userAssetAmount 以「最小單位」表示（假設 USDC decimals = 6）
      - 所以要除以 1_000_000 變成正常的 USDC 數字

    這個數字會對齊 Voltr 前端「My Position / Withdrawable」顯示，
    比你用 idle-only 計算的結果更接近實際可提領金額。
    """
    raw = get_voltr_user_balance_raw(vault_pubkey, user_pubkey)

    if not raw.get("success"):
        raise RuntimeError(f"Voltr API returned error: {raw}")

    user_asset_amount = raw["data"]["userAssetAmount"]
    withdrawable_usdc = user_asset_amount / 1_000_000  # USDC 6 decimals

    return withdrawable_usdc


# ==============================
# Optional Debug：交易帳戶列表 / 單帳戶資訊
# ==============================

def debug_tx_accounts(tx_sig: str) -> None:
    """
    給未來調其它 vault 用的 helper：

    印出某筆交易用到的所有 accountKeys，
    幫你快速找出哪些是 PDA / token account / program。
    """
    resp = rpc("getTransaction", [tx_sig, {"encoding": "json"}])
    raw_keys = resp["result"]["transaction"]["message"]["accountKeys"]

    # 兼容舊版（accountKeys 是 string）和新版（object with pubkey）
    normalized: List[str] = []
    for acc in raw_keys:
        if isinstance(acc, dict):
            normalized.append(acc["pubkey"])
        else:
            normalized.append(acc)

    print("\n=== Account Keys ===")
    for i, pubkey in enumerate(normalized):
        print(i, pubkey)


def debug_account(address: str) -> None:
    """
    調查單一帳戶的工具：

    - 看 owner（哪個 program 管理）
    - 看 data.program（例如 "spl-token"）
    - 若是 SPL Token，印出 mint / token owner / amount
    """
    info = get_account_info(address, encoding="jsonParsed")
    if not info:
        print(f"{address}: account not found")
        return

    print(f"\n=== {address} ===")
    print("owner (program id):", info.get("owner"))
    data = info.get("data", {})
    program = data.get("program")
    print("data.program:", program)

    if program == "spl-token":
        parsed = data.get("parsed", {})
        token_type = parsed.get("type")
        token_info = parsed.get("info", {})
        mint = token_info.get("mint")
        token_owner = token_info.get("owner")
        ui_amount = token_info.get("tokenAmount", {}).get("uiAmount")
        print("token type:", token_type)
        print("mint:", mint)
        print("token owner:", token_owner)
        print("amount (uiAmount):", ui_amount)


# ==============================
# Main：實際執行流程
# ==============================

if __name__ == "__main__":
    print("\n=== VECTIS / VOLTR VAULT DATA INSPECTOR ===")

    # 1) 先用「只看 idle」的方式算一次，當作對照組
    try:
        idle_info = get_user_withdrawable_idle_only(USER_LP_ATA)

        print("\n--- On-chain (idle-only estimation) ---")
        print(f"Vault NAV (USDC, idle only):  {idle_info['vault_nav_idle']:.6f}")
        print(f"LP Total Supply:              {idle_info['lp_supply']:.6f}")
        print(f"Your LP Amount:               {idle_info['user_lp']:.6f}")
        print(f"LP Price (idle NAV / LP):     {idle_info['lp_price_idle']:.6f}")
        print(f"Your Share of Vault (idle):   {idle_info['share_idle'] * 100:.6f} %")
        print(f"Your Withdrawable (idle est): {idle_info['withdrawable_idle']:.6f}")
        print(f"Idle USDC in Vault:           {idle_info['idle_usdc']:.6f}")
        print(f"Idle Ratio:                   {idle_info['idle_ratio'] * 100:.6f} %")
    except Exception as e:
        print("Error while fetching on-chain idle data:", e)

    # 2) 呼叫 Voltr API，拿「真實可提領 USDC」
    try:
        withdrawable_real = get_voltr_user_withdrawable_usdc(VAULT_PUBKEY, USER_WALLET)
        print("\n--- Voltr API (real user withdrawable) ---")
        print(f"Your Withdrawable (Voltr API): {withdrawable_real:.6f} USDC")
    except Exception as e:
        print("Error while calling Voltr API:", e)

    # 3) 列出 Vault token authority 底下的所有 token accounts（目前你會看到 idle USDC 那顆）
    try:
        print("\n--- Debug: Vault Token Accounts (by token authority) ---")
        list_vault_token_accounts_by_authority()
    except Exception as e:
        print("Error while listing vault token accounts:", e)

    print("\n=== DONE ===")
