"""
确定性优先层 (Deterministic Priority Layer)
高频简单请求走规则表/正则，不调LLM，降低延迟与成本。
"""

import re
import os
import time
import httpx
from typing import Optional

# ──────────────────────────────────────────────
# HS 编码格式验证
# HS编码: 4-10位数字，常用6位/8位/10位
# ──────────────────────────────────────────────
HS_CODE_PATTERN = re.compile(r"^\d{4,10}$")


def validate_hs_code(code: str) -> dict:
    """
    验证HS编码格式，返回确定性结果。

    Examples:
        >>> validate_hs_code("8541.40")
        {"valid": False, "reason": "HS code should contain only digits, got: 8541.40"}
        >>> validate_hs_code("854140")
        {"valid": True, "normalized": "854140", "length": 6}
    """
    code = code.strip().replace(".", "").replace(" ", "")
    if not HS_CODE_PATTERN.match(code):
        return {"valid": False, "reason": f"HS code should contain only digits, got: {code}"}
    return {
        "valid": True,
        "normalized": code,
        "length": len(code),
        "level": {4: "heading", 6: "subheading", 8: "national", 10: "statistical"}.get(len(code), "custom"),
    }


# ──────────────────────────────────────────────
# 常用国家代码映射表 (ISO 3166-1)
# ──────────────────────────────────────────────
COUNTRY_CODE_MAP = {
    "中国": ("CN", "CHN", "China"),
    "美国": ("US", "USA", "United States"),
    "德国": ("DE", "DEU", "Germany"),
    "英国": ("GB", "GBR", "United Kingdom"),
    "日本": ("JP", "JPN", "Japan"),
    "法国": ("FR", "FRA", "France"),
    "意大利": ("IT", "ITA", "Italy"),
    "西班牙": ("ES", "ESP", "Spain"),
    "荷兰": ("NL", "NLD", "Netherlands"),
    "比利时": ("BE", "BEL", "Belgium"),
    "加拿大": ("CA", "CAN", "Canada"),
    "澳大利亚": ("AU", "AUS", "Australia"),
    "印度": ("IN", "IND", "India"),
    "越南": ("VN", "VNM", "Vietnam"),
    "泰国": ("TH", "THA", "Thailand"),
    "韩国": ("KR", "KOR", "South Korea"),
    "巴西": ("BR", "BRA", "Brazil"),
    "墨西哥": ("MX", "MEX", "Mexico"),
    "俄罗斯": ("RU", "RUS", "Russia"),
    "土耳其": ("TR", "TUR", "Turkey"),
    "波兰": ("PL", "POL", "Poland"),
    "瑞典": ("SE", "SWE", "Sweden"),
    "瑞士": ("CH", "CHE", "Switzerland"),
    "阿联酋": ("AE", "ARE", "United Arab Emirates"),
    "沙特": ("SA", "SAU", "Saudi Arabia"),
    "南非": ("ZA", "ZAF", "South Africa"),
    "埃及": ("EG", "EGY", "Egypt"),
    "尼日利亚": ("NG", "NGA", "Nigeria"),
    "印度尼西亚": ("ID", "IDN", "Indonesia"),
    "马来西亚": ("MY", "MYS", "Malaysia"),
    "新加坡": ("SG", "SGP", "Singapore"),
    "菲律宾": ("PH", "PHL", "Philippines"),
    "巴基斯坦": ("PK", "PAK", "Pakistan"),
    "孟加拉国": ("BD", "BGD", "Bangladesh"),
    "阿根廷": ("AR", "ARG", "Argentina"),
    "智利": ("CL", "CHL", "Chile"),
    "哥伦比亚": ("CO", "COL", "Colombia"),
    "捷克": ("CZ", "CZE", "Czech Republic"),
    "罗马尼亚": ("RO", "ROU", "Romania"),
    "葡萄牙": ("PT", "PRT", "Portugal"),
    "希腊": ("GR", "GRC", "Greece"),
    "丹麦": ("DK", "DNK", "Denmark"),
    "芬兰": ("FI", "FIN", "Finland"),
    "挪威": ("NO", "NOR", "Norway"),
    "奥地利": ("AT", "AUT", "Austria"),
    "爱尔兰": ("IE", "IRL", "Ireland"),
    "以色列": ("IL", "ISR", "Israel"),
    "肯尼亚": ("KE", "KEN", "Kenya"),
    "摩洛哥": ("MA", "MAR", "Morocco"),
}

# 反向映射: 英文名/ISO2/ISO3 -> 中文
COUNTRY_REVERSE_MAP = {}
for cn, (iso2, iso3, en) in COUNTRY_CODE_MAP.items():
    COUNTRY_REVERSE_MAP[iso2.lower()] = cn
    COUNTRY_REVERSE_MAP[iso3.lower()] = cn
    COUNTRY_REVERSE_MAP[en.lower()] = cn


def lookup_country(query: str) -> dict:
    """
    确定性查询国家代码，支持中英文、ISO2/ISO3。

    Examples:
        >>> lookup_country("德国")
        {"found": True, "cn": "德国", "iso2": "DE", "iso3": "DEU", "en": "Germany"}
        >>> lookup_country("USA")
        {"found": True, "cn": "美国", "iso2": "US", "iso3": "USA", "en": "United States"}
    """
    q = query.strip()
    if q in COUNTRY_CODE_MAP:
        iso2, iso3, en = COUNTRY_CODE_MAP[q]
        return {"found": True, "cn": q, "iso2": iso2, "iso3": iso3, "en": en}
    rev = COUNTRY_REVERSE_MAP.get(q.lower())
    if rev:
        iso2, iso3, en = COUNTRY_CODE_MAP[rev]
        return {"found": True, "cn": rev, "iso2": iso2, "iso3": iso3, "en": en}
    return {"found": False, "query": q}


# ──────────────────────────────────────────────
# 货币汇率缓存（从公开API获取，带本地缓存）
# ──────────────────────────────────────────────
_RATE_CACHE: dict = {}  # {"USD_CNY": (rate, timestamp)}
_CACHE_TTL = 3600  # 1 hour

# 常用货币中文名映射
CURRENCY_NAME_MAP = {
    "USD": "美元",
    "CNY": "人民币",
    "EUR": "欧元",
    "GBP": "英镑",
    "JPY": "日元",
    "KRW": "韩元",
    "HKD": "港币",
    "SGD": "新加坡元",
    "AUD": "澳元",
    "CAD": "加元",
    "INR": "印度卢比",
    "RUB": "俄罗斯卢布",
    "BRL": "巴西雷亚尔",
    "TRY": "土耳其里拉",
    "THB": "泰铢",
    "VND": "越南盾",
    "MYR": "马来西亚林吉特",
    "IDR": "印尼盾",
    "AED": "阿联酋迪拉姆",
    "SAR": "沙特里亚尔",
    "ZAR": "南非兰特",
}


async def get_exchange_rate(base: str, target: str) -> dict:
    """
    获取汇率，优先走缓存，缓存过期则从公开API获取。
    使用 exchangerate-api.com 的免费开放接口（无需API Key）。

    Examples:
        >>> await get_exchange_rate("USD", "CNY")
        {"success": True, "base": "USD", "target": "CNY", "rate": 7.24, "source": "open.er-api.com"}
    """
    base = base.upper().strip()
    target = target.upper().strip()
    cache_key = f"{base}_{target}"

    # 检查缓存
    if cache_key in _RATE_CACHE:
        rate, ts = _RATE_CACHE[cache_key]
        if time.time() - ts < _CACHE_TTL:
            return {
                "success": True,
                "base": base,
                "target": target,
                "rate": rate,
                "source": "cache",
                "cached_at": ts,
            }

    # 从公开API获取
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://open.er-api.com/v6/latest/{base}")
            data = resp.json()
            if data.get("result") == "success" and target in data.get("rates", {}):
                rate = data["rates"][target]
                _RATE_CACHE[cache_key] = (rate, time.time())
                return {
                    "success": True,
                    "base": base,
                    "target": target,
                    "rate": rate,
                    "source": "open.er-api.com",
                    "updated_at": data.get("time_last_update_utc"),
                }
    except Exception:
        pass

    return {"success": False, "base": base, "target": target, "error": "Failed to fetch exchange rate"}


# ──────────────────────────────────────────────
# 邮箱 / 电话格式验证
# ──────────────────────────────────────────────
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# E.164 国际电话号码格式: +国家代码 号码
PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{6,14}$")


def validate_email(email: str) -> dict:
    """
    验证邮箱格式。

    Examples:
        >>> validate_email("contact@acme.com")
        {"valid": True, "email": "contact@acme.com"}
        >>> validate_email("bad-email")
        {"valid": False, "reason": "Invalid email format"}
    """
    email = email.strip()
    if EMAIL_PATTERN.match(email):
        return {"valid": True, "email": email}
    return {"valid": False, "reason": "Invalid email format", "input": email}


def validate_phone(phone: str) -> dict:
    """
    验证国际电话号码格式 (E.164)。

    Examples:
        >>> validate_phone("+8613800138000")
        {"valid": True, "phone": "+8613800138000", "country_code": "86"}
        >>> validate_phone("whatsapp:+491701234567")
        {"valid": True, "phone": "+491701234567", "country_code": "49"}
    """
    phone = phone.strip()
    # 去掉 whatsapp: 前缀
    if phone.lower().startswith("whatsapp:"):
        phone = phone[9:]
    # 去掉空格和短横线
    phone_clean = phone.replace(" ", "").replace("-", "")
    if PHONE_PATTERN.match(phone_clean):
        # 提取国家代码
        digits = phone_clean.lstrip("+")
        # 常见国家代码长度 1-3 位
        cc = ""
        for length in (3, 2, 1):
            prefix = digits[:length]
            if prefix in {"1", "7", "20", "27", "30", "31", "32", "33", "34", "36",
                          "39", "40", "41", "43", "44", "45", "46", "47", "48", "49",
                          "51", "52", "53", "54", "55", "56", "57", "58", "60", "61",
                          "62", "63", "64", "65", "66", "81", "82", "84", "86", "90",
                          "91", "92", "93", "94", "95", "98", "211", "212", "213",
                          "216", "218", "220", "221", "222", "223", "224", "225",
                          "226", "227", "228", "229", "230", "231", "232", "233",
                          "234", "235", "236", "237", "238", "239", "250", "251",
                          "252", "253", "254", "255", "256", "257", "258", "260",
                          "261", "262", "263", "264", "265", "266", "267", "268",
                          "269", "290", "291", "297", "298", "299", "350", "351",
                          "352", "353", "354", "355", "356", "357", "358", "359",
                          "370", "371", "372", "373", "374", "375", "376", "377",
                          "378", "380", "381", "382", "383", "385", "386", "387",
                          "389", "420", "421", "423", "500", "501", "502", "503",
                          "504", "505", "506", "507", "508", "509", "590", "591",
                          "592", "593", "594", "595", "596", "597", "598", "599",
                          "670", "672", "673", "674", "675", "676", "677", "678",
                          "679", "680", "681", "682", "683", "684", "685", "686",
                          "687", "688", "689", "690", "691", "692", "850", "852",
                          "853", "855", "856", "880", "886", "960", "961", "962",
                          "963", "964", "965", "966", "967", "968", "970", "971",
                          "972", "973", "974", "975", "976", "977", "992", "993",
                          "994", "995", "996", "998"}:
                cc = prefix
                break
        return {"valid": True, "phone": phone_clean, "country_code": cc or "unknown"}
    return {"valid": False, "reason": "Invalid phone format (expected E.164)", "input": phone}


# ──────────────────────────────────────────────
# PII 脱敏
# ──────────────────────────────────────────────
PII_EMAIL_PATTERN = re.compile(r"([a-zA-Z0-9._%+-])[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")
PII_PHONE_PATTERN = re.compile(r"(\+?\d{2})\d{4,}(\d{2})")


def mask_email(email: str) -> str:
    """脱敏邮箱: c***@acme.com"""
    match = re.match(r"([a-zA-Z0-9._%+-])[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", email)
    if match:
        return f"{match.group(1)}***@{match.group(2)}"
    return email


def mask_phone(phone: str) -> str:
    """脱敏电话: +86****00"""
    if len(phone) > 4:
        return phone[:3] + "****" + phone[-2:]
    return phone


def mask_pii(text: str) -> str:
    """自动脱敏文本中的邮箱和电话号码"""
    text = PII_EMAIL_PATTERN.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", text)
    text = PII_PHONE_PATTERN.sub(lambda m: f"{m.group(1)}****{m.group(2)}", text)
    return text


# ──────────────────────────────────────────────
# 确定性检查入口：判断请求是否能确定性回答
# ──────────────────────────────────────────────
def try_deterministic(tool_name: str, arguments: dict) -> Optional[dict]:
    """
    在调用真实工具前，先尝试确定性回答。
    如果命中，返回 dict 结果；否则返回 None，继续走正常工具流程。

    支持的确定性场景:
    - validate_hs_code: HS编码格式验证
    - lookup_country: 国家代码查询
    - validate_email: 邮箱格式验证
    - validate_phone: 电话格式验证
    """
    if tool_name == "validate_hs_code" and "code" in arguments:
        return validate_hs_code(arguments["code"])

    if tool_name == "lookup_country" and "query" in arguments:
        return lookup_country(arguments["query"])

    if tool_name == "validate_email" and "email" in arguments:
        return validate_email(arguments["email"])

    if tool_name == "validate_phone" and "phone" in arguments:
        return validate_phone(arguments["phone"])

    return None
