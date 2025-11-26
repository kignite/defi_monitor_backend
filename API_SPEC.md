# Defi Monitor API (Frontend Use)

Base URL (local dev): `http://127.0.0.1:8000`

## Health
- `GET /health`
- Response: `{"ok": true, "adapters": ["voltr"], "vaults": {"voltr": ["default"]}}`

## Frontend-Friendly Snapshot
- `POST /monitor`
- Purpose: frontends only send protocol + user; vault config comes from backend registry.
- Body (JSON):
  - `protocol` (string, default `"voltr"`): adapter name.
  - `user_wallet` (string, required): user wallet.
  - `vault_id` (string, optional): vault identifier; defaults to `"default"` per registry.
  - `lp_token_account` (string, optional): user LP ATA; if omitted and registry has `default_lp_token_account`, that is used; otherwise 400.
  - `include_token_accounts` (bool, default `false`): include token accounts debug.
- Response shape:
  ```json
  {
    "timestamp": 1234567890,
    "vault": { "pubkey": "...", "lp_mint": "...", "idle_usdc_ata": "...", "usdc_mint": "..." },
    "user": { "wallet": "...", "lp_token_account": "..." },
    "sources": {
      "onchain_idle": { "ok": true, "data": { /* idle metrics */ }, "error": null },
      "offchain": { "ok": true, "data": { /* adapter API data */ }, "error": null }
    },
    "meta": { "rpc_url": "...", "voltr_api_base": "...", "adapter": "voltr" },
    "debug": { "token_accounts": [...] }
  }
  ```
- Sample request:
  ```bash
  curl -X POST http://127.0.0.1:8000/monitor \
    -H "Content-Type: application/json" \
    -d '{"protocol":"voltr","user_wallet":"51pijqibmHQ17GZWjV8g8AyFWx1ZMmkUDtFR4Vz8Ah3F","include_token_accounts":true}'
  ```

## Default Snapshot (no input)
- `GET /snapshot`
- Query: `include_token_accounts` (bool), `adapter` (string, default `voltr`)
- Uses registry default vault/user.
- Response: same shape as `/monitor`.

## Advanced Snapshot (bring-your-own params)
- `POST /snapshot`
- Body: `adapter`, `vault_pubkey`, `lp_mint`, `idle_usdc_ata`, `usdc_mint`, `wallet`, `lp_token_account`, optional `rpc_url`, `voltr_api_base`, `include_token_accounts`.
- Response: same shape as `/monitor`.

## Source Fields
- `onchain_idle.data`: `{vault_nav_idle, lp_supply, user_lp, lp_price_idle, share_idle, withdrawable_idle, idle_ratio}`
- `offchain.data`: `{withdrawable_usdc, raw: <adapter API raw response>}`
- Each source has `ok`/`error` so UI can surface errors or degrade gracefully.

## Registry / Config
- Vault definitions are loaded from `config/vaults.json` (override path via `VAULT_CONFIG_PATH`).
- Frontend does not need vault addresses when using `/monitor` or `/snapshot` (GET); only `user_wallet` is required.
