from defi_monitor import VaultConfig, UserConfig, VoltrVaultMonitor

# Example configuration for the current Voltr vault + user
vault_cfg = VaultConfig(
    vault_pubkey="FajosXiYhqUDZ9cEB3pwS8n8pvcAbL3KzCGZnWDNvgLa",
    lp_mint="A5dvM5NKnuo6tmwoiEFC22qcXcUsa6mUoUtpkxjm1gKg",
    idle_usdc_ata="3AK6wAysksFRke6KJasnnL1sFn73jqhwDNquR2WhgrhE",
    usdc_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
)

user_cfg = UserConfig(
    wallet="51pijqibmHQ17GZWjV8g8AyFWx1ZMmkUDtFR4Vz8Ah3F",
    lp_token_account="BKCANLpd7r1k1dkki4Wj48kJZXd7CFFEzNnZXQGTrMk1",
)


def main() -> None:
    monitor = VoltrVaultMonitor()
    snap = monitor.snapshot(vault_cfg, user_cfg, include_token_accounts=True)

    print("=== Snapshot ===")
    print("Timestamp:", snap["timestamp"])
    print("Vault:", snap["vault"])
    print("User:", snap["user"])

    print("\n--- On-chain (idle-only) ---")
    print(snap["sources"]["onchain_idle"])

    print("\n--- Off-chain (adapter) ---")
    print(snap["sources"]["offchain"])

    if "debug" in snap:
        print("\n--- Debug: Token Accounts ---")
        print(snap["debug"].get("token_accounts"))


if __name__ == "__main__":
    main()
