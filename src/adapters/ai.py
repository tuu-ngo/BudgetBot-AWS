"""AI adapters for BudgetBot.

Interface:
    categorize(description, amount, date) -> {"category": str, "confidence": float}
    chat(message, context, transactions)  -> str
"""
import json
import re

from src.constants import CATEGORIES

# ---------------------------------------------------------------------------
# Few-shot examples — shown to the model every call.
# Covers clear cases AND ambiguous VN bank descriptions.
# ---------------------------------------------------------------------------
FEW_SHOT_EXAMPLES = [
    {"description": "HIGHLANDS COFFEE BUI VIEN", "amount": -65000,  "date": "2026-05-01", "category": "Food",          "confidence": 0.95},
    {"description": "SALARY DEPOSIT CREDIT",      "amount": 18500000,"date": "2026-05-05", "category": "Income",        "confidence": 0.98},
    {"description": "T1908 GRAB CITY",             "amount": -45000,  "date": "2026-05-06", "category": "Transport",     "confidence": 0.82},
    {"description": "NETFLIX SUBSCRIPTION",        "amount": -180000, "date": "2026-05-07", "category": "Subscriptions", "confidence": 0.97},
    {"description": "VINMART HCM 04",              "amount": -320000, "date": "2026-05-08", "category": "Shopping",      "confidence": 0.65},
    {"description": "EVN TPHCM TIEN DIEN",         "amount": -450000, "date": "2026-05-09", "category": "Utilities",     "confidence": 0.96},
    # FP-7 fix: VN bank refs → Transfer, not Other/0.12
    {"description": "FT0024112501 ID:0001",        "amount": -200000, "date": "2026-05-10", "category": "Transfer",      "confidence": 0.75},
    {"description": "VIETTEL INTERNET",            "amount": -299000, "date": "2026-05-11", "category": "Bills",         "confidence": 0.94},
    {"description": "CGV CINEMA VINCOM",           "amount": -150000, "date": "2026-05-12", "category": "Entertainment", "confidence": 0.93},
    {"description": "LONG CHAU PHARMACY",          "amount": -85000,  "date": "2026-05-13", "category": "Health",        "confidence": 0.91},
]

_EXAMPLES_TEXT = "\n".join(
    f'  {{"description": "{e["description"]}", "amount": {e["amount"]}, "date": "{e["date"]}"}} '
    f'→ {{"category": "{e["category"]}", "confidence": {e["confidence"]}}}'
    for e in FEW_SHOT_EXAMPLES
)

CATEGORIZE_PROMPT = """You are a Vietnamese bank transaction categorizer.

Categories (pick exactly one): {categories}

Rules:
- confidence is a float 0.0–1.0. Use < 0.60 only when the description is truly opaque.
- Negative amount = expense. Positive amount = income (likely "Income" or "Transfer").
- VN bank reference codes starting with FT, GD, IBFT, CK, DC → "Transfer", confidence 0.75.
- GRAB alone → "Transport". GRAB FOOD / GRABFOOD → "Food".
- Respond with JSON only. No explanation. No markdown.

Examples:
{examples}

Now categorize:
Transaction: "{description}"
Amount: {amount}
Date: {date}

{{"category": "<category>", "confidence": <0.0-1.0>}}"""


CHAT_SYSTEM_PROMPT = """You are BudgetBot, an AI personal finance coach.
You have access to the user's real spending data from their uploaded bank statements.
Answer questions specifically based on their data. Be concise and actionable.
If asked about amounts, cite the exact numbers from the spending context.
If the user asks something unrelated to personal finance, politely redirect.
Respond in the same language the user writes in (Vietnamese or English)."""


# ---------------------------------------------------------------------------
# FP-7: Pre-AI shortcut for opaque VN bank internal reference codes.
# Matches: FT24XXXXXXXX, GD0001, IBFT123, CK001, DC0123, etc.
# These are bank-generated internal transfer refs, not real merchant descriptions.
# ---------------------------------------------------------------------------
_VN_BANK_REF_RE = re.compile(
    r'^(?:FT|GD|IBFT|CK|DC|GCN|TT|UM)\d{4,}',
    re.IGNORECASE,
)


def _is_vn_bank_ref(description: str) -> bool:
    return bool(_VN_BANK_REF_RE.match(description.strip()))


# ---------------------------------------------------------------------------
# FP-6: Category normalization — strip whitespace + case-insensitive match.
# ---------------------------------------------------------------------------

def _normalize_category(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned in CATEGORIES:
        return cleaned
    lower = cleaned.lower()
    for cat in CATEGORIES:
        if cat.lower() == lower:
            return cat
    return "Other"


# ---------------------------------------------------------------------------
# FP-2: Robust JSON extraction.
# Iterates all {…} matches (not just the first) so that prose containing
# bare {…} blocks before the real JSON object doesn't cause a wrong match.
# FP-5: Missing confidence defaults to 0.80 (above threshold) instead of 0.5.
# FP-6: Category is normalized via _normalize_category.
# ---------------------------------------------------------------------------

def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?|```$", "", text, flags=re.MULTILINE).strip()

    for match in re.finditer(r"\{[^{}]+\}", text, re.DOTALL):
        try:
            obj = json.loads(match.group())
            if "category" not in obj:
                continue
            category = _normalize_category(str(obj["category"]))
            raw_conf = obj.get("confidence")
            if raw_conf is None:
                # Model returned a valid category but omitted confidence → assume confident
                confidence = 0.80
            else:
                try:
                    confidence = float(raw_conf)
                except (TypeError, ValueError):
                    confidence = 0.80
            return {"category": category, "confidence": max(0.0, min(1.0, confidence))}
        except json.JSONDecodeError:
            continue
    return {"category": "Other", "confidence": 0.0}


# ---------------------------------------------------------------------------
# Bedrock adapter
# ---------------------------------------------------------------------------

class BedrockAI:
    def __init__(self, region: str, model_id: str):
        import boto3
        self.runtime = boto3.client("bedrock-runtime", region_name=region)
        self.model_id = model_id

    def categorize(self, description: str, amount: float, date: str) -> dict:
        # FP-7: skip Bedrock entirely for opaque VN bank refs
        if _is_vn_bank_ref(description):
            return {"category": "Transfer", "confidence": 0.75}

        prompt = CATEGORIZE_PROMPT.format(
            categories=", ".join(CATEGORIES),
            examples=_EXAMPLES_TEXT,
            description=description,
            amount=amount,
            date=date,
        )
        resp = self.runtime.converse(
            modelId=self.model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            # FP-2: raised from 80 to 120 to prevent JSON truncation
            inferenceConfig={"maxTokens": 120, "temperature": 0.0},
        )
        text = resp["output"]["message"]["content"][0]["text"]
        return _parse_json_response(text)

    def chat(self, message: str, context: list[dict], transactions: list[dict]) -> str:
        spending_summary = _build_spending_summary(transactions)
        system_with_data = CHAT_SYSTEM_PROMPT
        if spending_summary:
            system_with_data += f"\n\nUser's spending data:\n{spending_summary}"

        messages = []
        for turn in context:
            messages.append({"role": turn["role"], "content": [{"text": turn["content"]}]})
        messages.append({"role": "user", "content": [{"text": message}]})

        resp = self.runtime.converse(
            modelId=self.model_id,
            system=[{"text": system_with_data}],
            messages=messages,
            inferenceConfig={"maxTokens": 512, "temperature": 0.7},
        )
        return resp["output"]["message"]["content"][0]["text"].strip()


# ---------------------------------------------------------------------------
# Local (rule-based) adapter — no AWS calls, for dev/testing
# ---------------------------------------------------------------------------

class LocalAI:
    """Keyword-based categorizer + simple chat stub. No AWS."""

    # FP-9: removed space-padded " be " — now handled via word-boundary matching below
    KEYWORDS: dict[str, list[str]] = {
        "Income":        ["salary", "deposit credit", "payroll", "incoming transfer"],
        "Transfer":      ["transfer to", "transfer from", "moved to savings"],
        "Subscriptions": ["subscription", "netflix", "spotify", "openai", "chatgpt",
                          "anthropic", "claude", "github", "icloud", "google one"],
        "Food":          ["restaurant", "cafe", "coffee", "starbucks", "highlands",
                          "phở", "pho", "food", "grab food", "grabfood", "shopee food",
                          "lunch", "dinner", "bakery", "banhmi", "bún"],
        "Transport":     ["grab", "uber", "be", "xanh sm", "taxi", "metro", "bus",
                          "petrol", "shell", "vinfast", "fuel", "xăng"],
        "Shopping":      ["shopee", "lazada", "tiki", "amazon", "store", "mall",
                          "vincom", "shop", "vinmart"],
        "Utilities":     ["electric", "evn", "water", "internet", "viettel", "vnpt",
                          "fpt", "utility", "tien dien", "tien nuoc"],
        "Bills":         ["insurance", "bao hiem", "rent", "tien thue", "management fee"],
        "Entertainment": ["cinema", "cgv", "lotte cinema", "concert", "game"],
        "Health":        ["pharmacy", "hospital", "clinic", "guardian", "long chau",
                          "medlatec", "nha thuoc"],
    }

    def categorize(self, description: str, amount: float, date: str) -> dict:
        # FP-7: fast-path for VN bank internal reference codes
        if _is_vn_bank_ref(description):
            return {"category": "Transfer", "confidence": 0.75}

        desc_lower = description.lower()
        for category, keywords in self.KEYWORDS.items():
            for kw in keywords:
                kw_clean = kw.strip()
                # FP-9: very short single-word keywords (≤2 chars, e.g. "be") use word-boundary
                # matching to avoid partial hits inside longer words (e.g. "uber" contains no
                # "be", but "describe" would — so \b is the safe guard).
                # Longer keywords and multi-word phrases keep plain substring matching, which
                # is intentional for VN bank descriptions like "EVNTPHCM".
                if len(kw_clean) <= 2 and " " not in kw_clean:
                    if re.search(r'\b' + re.escape(kw_clean) + r'\b', desc_lower):
                        return {"category": category, "confidence": 0.70}
                elif kw_clean in desc_lower:
                    return {"category": category, "confidence": 0.70}

        try:
            if float(amount) > 0:
                return {"category": "Income", "confidence": 0.60}
        except (TypeError, ValueError):
            pass
        return {"category": "Other", "confidence": 0.20}

    def chat(self, message: str, context: list[dict], transactions: list[dict]) -> str:
        spending_summary = _build_spending_summary(transactions)
        if spending_summary:
            return (
                f"[Local AI — no Bedrock]\n"
                f"Your message: '{message}'\n\n"
                f"Spending snapshot:\n{spending_summary}"
            )
        return (
            f"[Local AI — no Bedrock]\n"
            f"Your message: '{message}'\n"
            "No spending data found. Upload a bank statement first."
        )


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _build_spending_summary(transactions: list[dict]) -> str:
    """Aggregate transactions into a compact spending summary string."""
    if not transactions:
        return ""
    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    for t in transactions:
        cat = t.get("category", "Other")
        amt = t.get("amount", 0)
        totals[cat] = totals.get(cat, 0) + int(amt)
        counts[cat] = counts.get(cat, 0) + 1
    lines = []
    for cat, total in sorted(totals.items(), key=lambda kv: kv[1]):
        lines.append(f"  {cat}: {total:,} ({counts[cat]} transactions)")
    return "\n".join(lines)
