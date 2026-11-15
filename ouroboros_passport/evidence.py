import hashlib, json, time

class EvidenceClass:
    MEASURED = "MEASURED"
    UNKNOWN = "UNKNOWN"
    ABSTAIN = "ABSTAIN"
    NOT_RUN = "NOT_RUN"
    BLOCKED = "BLOCKED"
    ALL = (MEASURED, UNKNOWN, ABSTAIN, NOT_RUN, BLOCKED)

def now_utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def receipt_digest(obj):
    if not isinstance(obj, (str, bytes)):
        obj = canonical(obj)
    if isinstance(obj, str):
        obj = obj.encode("utf-8")
    return hashlib.sha256(obj).hexdigest()

class Evidence:
    def __init__(self, name, cls, value=None, source="", digest="", observed_at=None):
        self.name = name
        self.cls = cls
        self.value = value
        self.source = source
        self.digest = digest
        self.observed_at = observed_at or now_utc()

    def to_dict(self):
        d = {"name": self.name, "class": self.cls, "value": self.value,
             "source": self.source, "digest": self.digest, "observed_at": self.observed_at}
        return {k: v for k, v in d.items() if v not in ("", None)}

    @staticmethod
    def measured(name, value, source="", digest=""):
        return Evidence(name, EvidenceClass.MEASURED, value=value, source=source, digest=digest)

    @staticmethod
    def unknown(name):
        return Evidence(name, EvidenceClass.UNKNOWN)

    @staticmethod
    def abstain(name):
        return Evidence(name, EvidenceClass.ABSTAIN)

    @staticmethod
    def not_run(name):
        return Evidence(name, EvidenceClass.NOT_RUN)

    @staticmethod
    def blocked(name, reason=""):
        return Evidence(name, EvidenceClass.BLOCKED, value=reason)
