---
name: wiener-solana
description: Solana safety guardrails for Wiener Labs projects. Use when writing or reviewing any code that builds transactions, transfers funds, manages wallets or touches keypairs on Solana.
---

# Solana guardrails

These rules exist because real funds move through Wiener Labs systems. Violations are critical findings.

## Addresses

1. Never copy a destination address from transaction history or explorer pages. Address poisoning attacks plant lookalike addresses in wallet history. Destination addresses come only from a canonical config file, environment variable or verified constant.
2. When adding a new address constant, require the full address in the commit message so it can be independently verified.

## Amounts and math

3. All amounts are integer lamports or integer token base units. Conversion to UI units happens only at the display boundary.
4. USDC and most SPL tokens use 10^6 base units, SOL uses 10^9 lamports. Never assume decimals, read them from the mint when generic.

## Transactions

5. Simulate before sending whenever the flow allows it. Surface simulation failure reasons, do not retry blindly.
6. Set explicit priority fees from config, never hardcoded magic numbers.
7. Confirmations: money-moving flows wait for confirmed or finalized commitment as the flow requires, never processed.

## Keys and environments

8. Keypairs, seed phrases and private keys never appear in the repository, in code, in tests or in logs. Only environment variables or external signers.
9. Default cluster is devnet. Mainnet requires an explicit production flag, and code paths that differ per cluster must fail closed to devnet.
10. Vault or delegation pubkeys required at runtime must be validated at startup, not at first use.
