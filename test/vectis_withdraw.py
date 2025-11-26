import requests
from typing import Any, Dict, List, Optional

# === RPC & API Config ===
RPC = "https://api.mainnet-beta.solana.com"
VOLTR_API_BASE = "https://api.voltr.xyz"

# === Voltr Vault Config（這個 vault） ===
VAULT_STATE_PDA = "FajosXiYhqUDZ9cEB3pwS8n8pvcAbL3KzCGZnWDNvgLa"      # Voltr vault pubkey / state PDA
VAULT_LP_MINT = "A5dvM5NKnuo6tmwoiEFC22qcXcUsa6mUoUtpkxjm1gKg"        # LP mint
VAULT_IDLE_USDC_ATA = "3AK6wAysksFRke6KJasnnL1sFn73jqhwDNquR2WhgrhE"  # idle USDC token account
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# 你的錢包 & LP ATA
USER_WALLET = "51pijqibmHQ17GZWjV8g8AyFWx1ZMmkUDtFR4Vz8Ah3F"
USER_LP_ATA_DEFAULT = "BKCANLpd7r1k1dkki4Wj48kJZXd7CFFEzNnZXQGTrMk1"


# === Solana RPC Helpers ===
def rpc(method: str, params: List[Any]) -> Dict[str, Any]:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    r = requests.post(RPC, json=payload)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data


def get_token_balance(account: str) -> float:
    r = rpc("getTokenAccountBalance", [account])
    value = r.get("result", {}).get("value")
    if not value:
        return 0.0
    return float(value.get("uiAmount", 0.0))


def get_token_supply(mint: str) -> float:
    r = rpc("getTokenSupply", [mint])
    value = r.get("result", {}).get("value")
    if not value:
        return 0.0
    return float(value.get("uiAmount", 0.0))


def get_account_info(address: str, encoding: str = "base64") -> Optional[Dict[str, Any]]:
    r = rpc("getAccountInfo", [address, {"encoding": encoding}])
    return r.get("result", {}).get("value")


# === 找出真正的 token authority（你剛剛已經跑過一次） ===
def get_vault_token_authority() -> str:
    info = get_account_info(VAULT_IDLE_USDC_ATA, encoding="jsonParsed")
    if not info:
        raise RuntimeError("Idle USDC ATA not found")

    parsed = info["data"]["parsed"]
    owner = parsed["info"]["owner"]
    return owner


def get_token_accounts_by_owner(owner: str) -> List[Dict[str, Any]]:
    r = rpc(
        "getTokenAccountsByOwner",
        [
            owner,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"},
        ],
    )
    return r.get("result", {}).get("value", [])


# === On-chain NAV（只看 idle 的版本） ===
def get_vault_idle_usdc() -> float:
    return get_token_balance(VAULT_IDLE_USDC_ATA)


def get_vault_nav_onchain_only() -> float:
    # 目前只含 idle；真正 NAV 會遠大於這個數字
    return get_vault_idle_usdc()


def get_user_lp_amount(user_lp_ata: str) -> float:
    return get_token_balance(user_lp_ata)


def get_lp_price_and_share_onchain(user_lp_ata: str) -> Dict[str, float]:
    vault_nav = get_vault_nav_onchain_only()
    lp_supply = get_token_supply(VAULT_LP_MINT)
    user_lp = get_user_lp_amount(user_lp_ata)

    if lp_supply <= 0:
        return {
            "vault_nav": vault_nav,
            "lp_supply": lp_supply,
            "user_lp": user_lp,
            "lp_price": 0.0,
            "share": 0.0,
        }

    lp_price = vault_nav / lp_supply
    share = user_lp / lp_supply

    return {
        "vault_nav": vault_nav,
        "lp_supply": lp_supply,
        "user_lp": user_lp,
        "lp_price": lp_price,
        "share": share,
    }


def get_user_withdrawable_onchain(user_lp_ata: str) -> Dict[str, float]:
    base = get_lp_price_and_share_onchain(user_lp_ata)

    vault_nav = base["vault_nav"]
    lp_supply = base["lp_supply"]
    user_lp = base["user_lp"]
    lp_price = base["lp_price"]
    share = base["share"]

    withdrawable = user_lp * lp_price
    idle_usdc = get_vault_idle_usdc()
    idle_ratio = (idle_usdc / vault_nav) if vault_nav > 0 else 0.0

    return {
        "vault_nav": vault_nav,
        "lp_supply": lp_supply,
        "user_lp": user_lp,
        "lp_price": lp_price,
        "share": share,
        "withdrawable": withdrawable,
        "idle_usdc": idle_usdc,
        "idle_ratio": idle_ratio,
    }


# === Voltr REST API：真正的 NAV / user balance ===
def get_voltr_user_balance(vault_pubkey: str, user_pubkey: str) -> Dict[str, Any]:
    """
    打 Voltr 官方 API:
      GET /vault/{pubkey}/user/{userPubkey}/balance

    回傳格式官方沒在 docs 寫死，我這裡先把整包 JSON 回傳給你，
    你可以 print 出來看 field 名稱，再微調 parsing。
    """
    url = f"{VOLTR_API_BASE}/vault/{vault_pubkey}/user/{user_pubkey}/balance"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    return data


def get_voltr_share_price(vault_pubkey: str) -> Optional[float]:
    """
    可選：如果你想拿官方計算的 share price（asset per LP），
    可以打 /vault/{pubkey}/share-price
    """
    url = f"{VOLTR_API_BASE}/vault/{vault_pubkey}/share-price"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    # 這裡不知道欄位名，先直接印出來給你看
    return data  # 你可以改成 return data["sharePrice"] 之類的

def get_voltr_user_withdrawable_usdc(vault_pubkey: str, user_pubkey: str) -> float:
    """
    用 Voltr API 取得真實可提領 USDC 數量（含外部倉位 NAV）
    """
    url = f"https://api.voltr.xyz/vault/{vault_pubkey}/user/{user_pubkey}/balance"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()

    # 確保成功
    if not data.get("success"):
        raise RuntimeError(f"Voltr API returned error: {data}")

    raw_amount = data["data"]["userAssetAmount"]

    # 依照 USDC decimals 轉成浮點
    return raw_amount / 1_000_000


# === Debug：列出 authority 底下所有 token accounts ===
def list_vault_token_accounts_by_authority() -> None:
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


# === CLI Entry ===
if __name__ == "__main__":
    USER_LP_ATA = USER_LP_ATA_DEFAULT

    print("\n=== VECTIS / VOLTR VAULT MONITOR ===")

    # 1) 純鏈上（只看 idle）的版本
    try:
        onchain = get_user_withdrawable_onchain(USER_LP_ATA)

        print("\n--- On-chain (idle only) ---")
        print(f"Vault NAV (USDC, idle only): {onchain['vault_nav']:.6f}")
        print(f"LP Total Supply:             {onchain['lp_supply']:.6f}")
        print(f"Your LP Amount:              {onchain['user_lp']:.6f}")
        print(f"LP Price (USDC/LP):          {onchain['lp_price']:.6f}")
        print(f"Your Share of Vault:         {onchain['share'] * 100:.6f} %")
        print(f"Your Withdrawable (idle):    {onchain['withdrawable']:.6f}")
        print(f"Idle USDC in Vault:          {onchain['idle_usdc']:.6f}")
        print(f"Idle Ratio:                  {onchain['idle_ratio'] * 100:.6f} %")
    except Exception as e:
        print("Error while fetching on-chain data:", e)

    # 2) Voltr 官方 API：真正的 vault balance（含外部倉位）
    try:
        api_balance = get_voltr_user_balance(VAULT_STATE_PDA, USER_WALLET)
        print("\n--- Voltr API: /vault/{vault}/user/{user}/balance ---")
        print("Raw JSON response:")
        print(api_balance)
    except Exception as e:
        print("Error while calling Voltr API:", e)

    # 3) Debug: authority token accounts
    try:
        print("\n--- Debug: Vault Token Accounts (by token authority) ---")
        list_vault_token_accounts_by_authority()
    except Exception as e:
        print("Error while listing vault token accounts:", e)
