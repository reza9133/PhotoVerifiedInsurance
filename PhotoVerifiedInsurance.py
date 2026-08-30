# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from dataclasses import dataclass
from datetime import datetime, timezone

SEVERITY_PAYOUT_BPS = {
    "none": 0,
    "low": 2500,     # 25%
    "medium": 6000,  # 60%
    "high": 10000,   # 100%
}

@gl.evm.contract_interface
class _Recipient:
    class View:
        pass
    class Write:
        pass

@allow_storage
@dataclass
class Pool:
    owner: Address
    name: str
    criteria: str
    premium: u256
    max_payout: u256
    balance: u256
    active: bool

@allow_storage
@dataclass
class Policy:
    pool_id: u256
    holder: Address
    purchased_at: str
    active: bool

@allow_storage
@dataclass
class Claim:
    policy_id: u256
    pool_id: u256
    incident_description: str
    status: str    # "pending" | "approved" | "denied"
    severity: str  # "none" | "low" | "medium" | "high"
    assessment: str
    payout_amount: u256
    filed_at: str

class PhotoVerifiedInsurance(gl.Contract):
    pools: TreeMap[u256, Pool]
    next_pool_id: u256
    policies: TreeMap[u256, Policy]
    next_policy_id: u256
    claims: TreeMap[u256, Claim]
    next_claim_id: u256

    def __init__(self):
        self.next_pool_id = u256(0)
        self.next_policy_id = u256(0)
        self.next_claim_id = u256(0)

    @gl.public.write.payable
    def create_pool(
        self, name: str, criteria: str, premium: u256, max_payout: u256
    ) -> u256:
        seed = gl.message.value
        if seed == u256(0):
            raise gl.vm.UserError("[EXPECTED] pool must be seeded with GEN")
        if len(criteria.strip()) == 0:
            raise gl.vm.UserError("[EXPECTED] criteria must not be empty")
        if premium == u256(0):
            raise gl.vm.UserError("[EXPECTED] premium must be greater than zero")
        if max_payout == u256(0):
            raise gl.vm.UserError("[EXPECTED] max_payout must be greater than zero")

        pool_id = self.next_pool_id
        self.next_pool_id = self.next_pool_id + 1

        self.pools[pool_id] = Pool(
            owner=gl.message.sender_address,
            name=name,
            criteria=criteria,
            premium=premium,
            max_payout=max_payout,
            balance=seed,
            active=True,
        )
        return pool_id

    @gl.public.write.payable
    def fund_pool(self, pool_id: u256) -> None:
        if pool_id not in self.pools:
            raise gl.vm.UserError("[EXPECTED] pool not found")
        value = gl.message.value
        if value == u256(0):
            raise gl.vm.UserError("[EXPECTED] must send GEN to fund the pool")
        self.pools[pool_id].balance = self.pools[pool_id].balance + value

    @gl.public.write
    def withdraw_pool_balance(self, pool_id: u256, amount: u256) -> None:
        if pool_id not in self.pools:
            raise gl.vm.UserError("[EXPECTED] pool not found")

        pool = self.pools[pool_id]
        if gl.message.sender_address != pool.owner:
            raise gl.vm.UserError("[EXPECTED] only the pool owner may withdraw")
        if amount == u256(0):
            raise gl.vm.UserError("[EXPECTED] amount must be greater than zero")
        if amount > pool.balance:
            raise gl.vm.UserError("[EXPECTED] amount exceeds pool balance")

        self.pools[pool_id].balance = pool.balance - amount
        _Recipient(pool.owner).emit_transfer(value=amount)

    @gl.public.write.payable
    def buy_policy(self, pool_id: u256) -> u256:
        if pool_id not in self.pools:
            raise gl.vm.UserError("[EXPECTED] pool not found")

        pool = self.pools[pool_id]
        if not pool.active:
            raise gl.vm.UserError("[EXPECTED] pool is not active")

        paid = gl.message.value
        if paid != pool.premium:
            raise gl.vm.UserError(
                f"[EXPECTED] premium mismatch: expected {pool.premium}, got {paid}"
            )

        policy_id = self.next_policy_id
        self.next_policy_id = self.next_policy_id + 1

        self.policies[policy_id] = Policy(
            pool_id=pool_id,
            holder=gl.message.sender_address,
            purchased_at=datetime.now(timezone.utc).isoformat(),
            active=True,
        )
        self.pools[pool_id].balance = self.pools[pool_id].balance + paid
        return policy_id

    @gl.public.write
    def file_claim(
        self, policy_id: u256, incident_description: str, photo_url: str
    ) -> u256:
        if policy_id not in self.policies:
            raise gl.vm.UserError("[EXPECTED] policy not found")

        policy = self.policies[policy_id]
        if gl.message.sender_address != policy.holder:
            raise gl.vm.UserError("[EXPECTED] only the policyholder may file a claim")
        if not policy.active:
            raise gl.vm.UserError("[EXPECTED] policy is not active or already used")
        if len(photo_url.strip()) == 0:
            raise gl.vm.UserError("[EXPECTED] a photo url is required")

        # ابطال بیمه‌نامه برای جلوگیری از ارسال تکراری
        self.policies[policy_id].active = False

        pool_id = policy.pool_id
        pool = self.pools[pool_id]
        criteria = pool.criteria

        def leader_fn():
            img_response = gl.nondet.web.get(photo_url)
            photo_bytes = img_response.body

            prompt = f"""
            You are a parametric insurance claims validator.

            Coverage criteria for this pool:
            {criteria}

            Policyholder's incident description:
            {incident_description}

            Examine the attached photo evidence. Decide whether it credibly
            supports the incident description under the coverage criteria,
            and rate the severity of the damage or loss shown.

            Respond ONLY as JSON in this exact shape:
            {{"approved": true/false, "severity": "none"/"low"/"medium"/"high", "assessment": "one or two sentence explanation"}}
            Use severity "none" whenever approved is false.
            It is mandatory that you respond only using the JSON format above,
            with no other words, characters, or markdown formatting.
            """
            result = gl.nondet.exec_prompt(
                prompt, images=[photo_bytes], response_format="json"
            )
            if not isinstance(result, dict) or "approved" not in result:
                raise gl.vm.UserError("[LLM_ERROR] malformed LLM response")
            severity = str(result.get("severity", "none")).lower()
            if severity not in SEVERITY_PAYOUT_BPS:
                severity = "none"
            return {
                "approved": bool(result["approved"]),
                "severity": severity,
                "assessment": str(result.get("assessment", "")),
            }

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            validator_result = leader_fn()
            return (
                validator_result["approved"] == leaders_res.calldata["approved"]
                and validator_result["severity"] == leaders_res.calldata["severity"]
            )

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        claim_id = self.next_claim_id
        self.next_claim_id = self.next_claim_id + 1

        approved = result["approved"]
        severity = result["severity"]
        bps = SEVERITY_PAYOUT_BPS[severity]
        payout_amount = u256((int(pool.max_payout) * bps) // 10000)

        status = "denied"
        if approved and payout_amount > u256(0):
            if payout_amount > pool.balance:
                payout_amount = pool.balance
            if payout_amount > u256(0):
                status = "approved"
                self.pools[pool_id].balance = pool.balance - payout_amount
                _Recipient(policy.holder).emit_transfer(value=payout_amount)
        elif approved:
            status = "approved"

        updated_pool = self.pools[pool_id]

        self.claims[claim_id] = Claim(
            policy_id=policy_id,
            pool_id=pool_id,
            incident_description=incident_description,
            status=status,
            severity=severity,
            assessment=result["assessment"],
            payout_amount=payout_amount,
            filed_at=datetime.now(timezone.utc).isoformat(),
        )
        return claim_id

    @gl.public.view
    def get_pool(self, pool_id: u256) -> dict:
        if pool_id not in self.pools:
            raise gl.vm.UserError("[EXPECTED] pool not found")
        pool = self.pools[pool_id]
        return {
            "owner": str(pool.owner),
            "name": pool.name,
            "criteria": pool.criteria,
            "premium": str(pool.premium),
            "max_payout": str(pool.max_payout),
            "balance": str(pool.balance),
            "active": pool.active,
        }

    @gl.public.view
    def get_policy(self, policy_id: u256) -> dict:
        if policy_id not in self.policies:
            raise gl.vm.UserError("[EXPECTED] policy not found")
        policy = self.policies[policy_id]
        return {
            "pool_id": str(policy.pool_id),
            "holder": str(policy.holder),
            "purchased_at": policy.purchased_at,
            "active": policy.active,
        }

    @gl.public.view
    def get_claim(self, claim_id: u256) -> dict:
        if claim_id not in self.claims:
            raise gl.vm.UserError("[EXPECTED] claim not found")
        claim = self.claims[claim_id]
        return {
            "policy_id": str(claim.policy_id),
            "pool_id": str(claim.pool_id),
            "incident_description": claim.incident_description,
            "status": claim.status,
            "severity": claim.severity,
            "assessment": claim.assessment,
            "payout_amount": str(claim.payout_amount),
            "filed_at": claim.filed_at,
        }

    @gl.public.view
    def get_total_pools(self) -> u256:
        return self.next_pool_id

    @gl.public.view
    def get_total_claims(self) -> u256:
        return self.next_claim_id
