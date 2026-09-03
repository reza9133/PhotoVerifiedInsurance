# 🛡️ PhotoVerifiedInsurance — Trustless Parametric Micro-Insurance

> A fully decentralized parametric micro-insurance protocol built on **GenLayer**. It eliminates traditional human claims adjusters by leveraging decentralized AI-validator consensus to evaluate photographic evidence directly against custom natural-language coverage criteria.

---

## 🌟 Overview

Traditional insurance claims processing is plagued by human bottlenecks, subjective disputes, and high administrative overhead. **PhotoVerifiedInsurance** re-imagines micro-insurance by using GenLayer's **Intelligent Contracts** and **Optimistic Democracy** consensus mechanism. 

Policyholders submit photographic evidence of an incident alongside a description. Instead of a human adjuster, a decentralized network of independent AI validators examines the photo against the pool's natural-language rules, reaches consensus on approval and damage severity, and triggers an **instant, trustless smart payout**.

---

## ⚙️ Core Architecture & Flow

1. **`create_pool(...)`**: Anyone can establish a coverage pool, seeding it with native GEN tokens and defining (in natural language) what constitutes a valid, coverable incident (`criteria`), along with a fixed `premium` and `max_payout`.
2. **`buy_policy(...)`**: Users pay the fixed premium in GEN to enroll in a specific coverage pool. The contract strictly enforces solvency, blocking new sales if the pool lacks the reserved capacity to honor the payout.
3. **`file_claim(...)`**: The policyholder submits their policy ID, an incident description, and a photo URL (e.g., stored via IPFS/Pinata). 
   - **AI-Validator Consensus:** The leader node fetches the image via `gl.nondet.web.get` and passes it to a vision-capable LLM (`gl.nondet.exec_prompt` with images) to evaluate it against the coverage criteria.
   - **Discrete Severity Tiers:** To ensure precise consensus without raw float discrepancies, severity is categorized into discrete tiers (`none`, `low`, `medium`, `high`), mapped deterministically via Basis Points (`SEVERITY_PAYOUT_BPS`).
4. **Instant Automated Payout**: Approved claims immediately trigger a trustless transfer of funds to the policyholder's wallet using GenLayer's Ghost Contract mechanics (`_Recipient.emit_transfer`).

---

## 🧠 Why GenLayer?

- **Native Web & Image Access:** Contracts can securely fetch external assets (like IPFS photo URLs) and pass them to multi-modal LLMs without relying on external oracles.
- **The Equivalence Principle:** Solves AI non-determinism by having validators independently re-run the assessment and compare core decision fields (`approved` and `severity`), ensuring cryptographic agreement even when reasoning assessments differ in wording.
- **Guaranteed Solvency (Liability Tracking):** Through O(1) state tracking (`reserved_balance`), the protocol guarantees that pool owners can never withdraw funds that are backing active policies.

---

## 📂 Contract Specification

### Main Methods

| Method | Type | Description |
| :--- | :--- | :--- |
| `create_pool(name, criteria, premium, max_payout)` | Write (Payable) | Creates a new insurance pool seeded with initial GEN liquidity. |
| `fund_pool(pool_id)` | Write (Payable) | Adds more GEN liquidity to an existing pool. |
| `withdraw_pool_balance(pool_id, amount)` | Write | Allows the pool owner to withdraw excess funds (free balance only). |
| `buy_policy(pool_id)` | Write (Payable) | Purchases coverage by paying the exact pool premium. |
| `file_claim(policy_id, description, photo_url)` | Write | Submits a claim with a photo, triggers AI consensus, and auto-pays if approved. |
| `get_pool(pool_id)` | View | Returns pool details, active status, balance, and reserved liabilities. |
| `get_policy(policy_id)` | View | Returns policy status and ownership info. |
| `get_claim(claim_id)` | View | Returns claim decision, severity tier, assessment, and payout amount. |
| `get_total_pools()` | View | Returns the total number of pools created. |
| `get_total_claims()` | View | Returns the total number of claims filed. |

---

## 🚀 Getting Started & Testing (GenLayer Studio)

1. **Deploy:** Load `PhotoVerifiedInsurance.py` into [GenLayer Studio](https://studio.genlayer.com).
2. **Setup Validators:** Ensure your active validators support vision models (e.g., `gpt-4o`, `claude-3-5-sonnet`).
3. **Create a Pool:** 
   - *Arguments:* Name (`"Car Dent Insurance"`), Criteria (`"Covers visible dents..."`), Premium (`1000000000000000000`), Max Payout (`5000000000000000000`).
   - *Value (GEN):* `10` (Must be $\ge$ Max Payout to guarantee the first policy).
4. **Buy Policy:** Switch to a buyer account, call `buy_policy` with `pool_id = 0` and *Value (GEN)* = `1`.
5. **File Claim:** Call `file_claim` with `policy_id = 0`, a description, and an image URL (e.g., from your Pinata IPFS gateway).

---

## 🔒 Security & Best Practices

- **O(1) Liability Tracking:** The pool dynamically maintains a `reserved_balance` to guarantee active policies can always be paid out. Withdrawals and new policy sales are blocked if they compromise pool solvency.
- **State Mutation Safety:** All deterministic state changes (e.g., updating balances, revoking policies) occur strictly *after* the `run_nondet_unsafe` consensus block, preventing node divergence—a golden standard for GenVM.
- **Double-Claim Prevention:** Automatically invalidates a policy (`policy.active = False`) the moment a claim is resolved, preventing spam or retry attacks.
- **Checks-Effects-Interactions:** State balances are safely updated prior to executing external token transfers.
- **Strict Error Handling:** Malformed LLM outputs trigger a validator disagreement (`False`), forcing a leader rotation rather than trusting broken data.

---

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).
