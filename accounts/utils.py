import re

def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_abnormal_value(result_value, normal_range):
    """
    Always returns True or False.
    Supported normal_range:
      3.5-5.5
      >= 10
      <= 200
      positive
      negative
    """
    rv = (result_value or "").strip()
    nr = (normal_range or "").strip()

    if not rv or not nr:
        return False

    rv_low = rv.lower()
    nr_low = nr.lower()

    # Text values
    if nr_low in ["positive", "negative"]:
        return rv_low != nr_low

    # Numeric result: extract first number
    match = re.search(r"[-+]?\d+(\.\d+)?", rv)
    if not match:
        return False

    val = _to_float(match.group(0))
    if val is None:
        return False

    # Range: 3.5-5.5
    match = re.match(r"^\s*([-+]?\d+(\.\d+)?)\s*-\s*([-+]?\d+(\.\d+)?)\s*$", nr)
    if match:
        low = _to_float(match.group(1))
        high = _to_float(match.group(3))
        if low is None or high is None:
            return False
        return not (low <= val <= high)

    # Comparator: >= 10, > 10, <= 10, < 10
    match = re.match(r"^\s*(>=|>|<=|<)\s*([-+]?\d+(\.\d+)?)\s*$", nr)
    if match:
        op = match.group(1)
        lim = _to_float(match.group(2))
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

    return False