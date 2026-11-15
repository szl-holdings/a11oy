from .evidence import canonical, receipt_digest

PASSPORT_VERSION = "ouroboros-passport/0.1"

class Passport:
    """Content-addressed model passport. digest = sha256 over canonical JSON of all fields except digest."""
    def __init__(self, model_id, tenant, sections, parents=None, created_at="", revision="r1"):
        self.model_id = model_id
        self.tenant = tenant
        self.sections = sections
        self.parents = parents or []
        self.created_at = created_at
        self.revision = revision

    def base_dict(self):
        return {"passport_version": PASSPORT_VERSION, "model_id": self.model_id,
                "tenant": self.tenant, "revision": self.revision, "created_at": self.created_at,
                "parents": self.parents, "sections": self.sections}

    def compute_digest(self):
        return receipt_digest(self.base_dict())

    def to_dict(self):
        d = self.base_dict()
        d["digest"] = self.compute_digest()
        return d
