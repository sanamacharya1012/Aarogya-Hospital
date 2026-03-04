import re

def _to_float(s: str):
    try:
        return float(s)
    except Exception:
        return None

def is_abnormal_value(result_value: str, normal_range: str) -> bool:
    """
    Supported normal_range formats:
        - "3.5-5.5"
        - ">=10" or "> 10"
        - "<=200" or "< 200"
        - "negative" / "positive" ( case-insensitive )
    If can't parse, returns False (unknown).
    """
    rv = (result_value or "").strip()
    nr = (normal_range or "").strip()

    if not rv or not nr:
        return False
    
    rv_low = rv.lower()
    nr_low = nr.lower()

    # Text-based results
    if nr_low in ["positive", "negative"]:
        # abnormal if they don't match
        return rv_low !=nr_low
    
    # Numeric result extraction
    # Allow results like "12", "12.5", "12 mg/dL" -> take first number
    m = re.search(r"[-+]?\d+(|.|d+)?", rv)
    if not m:
        return False
    
    val = _to_float(m.group(0))
    if val is None:
        return False
    
    # range "a-b"
    m2 = re.match(r"^\s*([-+]?\d+(\.\d+)?)\s*-\s*([-+]?\d+(\.\d+)?)\s*$", nr)
    if m2:
        low = _to_float(m2.group(1))
        high = _to_float(m2.group(3))
        if low is None or high is None:
            return False
        return not (low <= val <= high)
    
    # comparators
    m3 = re.match(r"^\s*(>=|>|<=|<)\s*([-+]?\d+(\.\d+)?)\s*$", nr)
    if m3:
        op = m3.group(1)
        lim = _to_float(m3.group(2))
        if lim is None:
            return False
        if op == ">":
            return not (val > lim)
        if op == ">=":
            return not (val >= lim)
        if op == "<":
            return not (val < lim)
        if op == "<=":
            return not (val <= lim)
        
        # Unknown format
        return False