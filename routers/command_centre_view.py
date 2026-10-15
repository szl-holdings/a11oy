#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Pure Python presentation components for the existing command centre.

Taxonomy: services/presentation. No network, filesystem, credential, signer or
action access. Strings are text, never markup. Browser actions remain in the
existing, separately source-bound JavaScript client.
"""

import hashlib
import html
import json
import re
from dataclasses import dataclass
from urllib.parse import urlsplit


_TAGS = frozenset("html head meta title link script body a div aside p nav main header h1 h2 h3 button section article code small span form label input textarea select option details summary pre strong ol li footer noscript dl dt dd".split())
_VOID = frozenset({"meta", "link", "input"})
_ATTRS = frozenset("id class lang charset name content href rel src defer type autocomplete spellcheck placeholder rows maxlength required value readonly disabled hidden selected for role".split())
_ORIGINS = frozenset({"github.com", "huggingface.co", "a11oy.net", "a-11-oy.com"})


def safe_href(value):
    """Accept canonical HTTPS origins or unambiguous same-origin paths only."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise ValueError("invalid link")
    if any(ord(char) <= 32 or ord(char) >= 127 for char in value):
        raise ValueError("invalid link")
    if any(char in value for char in ("\\", "%", "<", ">", '"', "'")):
        raise ValueError("invalid link")
    if value.startswith("#"):
        if not re.fullmatch(r"#[a-z][a-z0-9-]*", value):
            raise ValueError("invalid fragment")
        return value
    parsed = urlsplit(value)
    if value.startswith("/"):
        if value.startswith("//") or parsed.scheme or parsed.netloc:
            raise ValueError("invalid relative link")
    elif parsed.scheme != "https" or parsed.netloc not in _ORIGINS:
        raise ValueError("unapproved link origin")
    if any(part in {".", ".."} for part in parsed.path.split("/")):
        raise ValueError("ambiguous link path")
    return value


@dataclass(frozen=True)
class Element:
    tag: str
    children: tuple
    attributes: tuple

    def render(self):
        attributes = []
        for key, value in self.attributes:
            if value is None or value is False:
                continue
            if value is True:
                attributes.append(f" {key}")
            else:
                attributes.append(f' {key}="{html.escape(str(value), quote=True)}"')
        start = "<" + self.tag + "".join(attributes) + ">"
        if self.tag in _VOID:
            return start
        body = "".join(child.render() if isinstance(child, Element)
                       else html.escape(str(child), quote=True)
                       for child in self.children if child is not None)
        return start + body + "</" + self.tag + ">"


def node(tag, *children, **attributes):
    if tag not in _TAGS:
        raise ValueError("unapproved element")
    if tag == "script" and (children or attributes.get("src") != "/command-centre/app.js"):
        raise ValueError("only the retained external action client is admitted")
    checked = []
    for name, value in attributes.items():
        name = name.rstrip("_").replace("_", "-")
        if name not in _ATTRS and not re.fullmatch(r"(?:aria|data)-[a-z][a-z0-9-]*", name):
            raise ValueError("unapproved attribute")
        if name in {"href", "src"}:
            value = safe_href(value)
        if name == "src" and (tag != "script" or value != "/command-centre/app.js"):
            raise ValueError("unapproved script")
        checked.append((name, value))
    if tag in _VOID and children:
        raise ValueError("void element cannot have children")
    return Element(tag, children, tuple(checked))


def _head(number, title, label=None):
    return node("div", node("div", node("p", number, class_="eyebrow"),
                           node("h2", title)),
                node("span", label, class_="label") if label else None,
                class_="section-head")


def _link_card(title, href, boundary):
    return node("a", node("strong", title), node("span", boundary),
                href=href, class_="link-card")


def _links(model, lane):
    rows = model.get("surfaces")
    if not isinstance(rows, list) or len(rows) > 64:
        raise ValueError("invalid surface model")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid surface")
        if row.get("lane") != lane:
            continue
        if any(not isinstance(row.get(key), str) or len(row[key]) > 2048
               for key in ("title", "href", "boundary")):
            raise ValueError("invalid surface field")
        result.append(_link_card(row["title"], row["href"], row["boundary"]))
    return result


def _ownership(model):
    estate = model.get("public_estate", {})
    available = estate.get("state") == "SOURCE_CONTRACT"
    cards = []
    if available:
        canonical = estate["canonical"]
        cards = [
            _link_card("Python product source", canonical["source"], "A11oy owns the product runtime; source publication is not execution approval."),
            _link_card("Hugging Face artifacts", canonical["huggingFaceOrganization"], "Existing models, datasets and Spaces retain their owners and qualification gates."),
            _link_card("Product origin", canonical["product"], "One product entry point. Existing actions retain their own authentication and policy."),
            _link_card("Proof origin", canonical["proof"], "Source-bound evidence has its own date and verification boundary."),
        ]
        ayllu = estate["ayllu"]
        cards.append(_link_card("Ayllu · inventory only", ayllu["href"],
            "INVENTORY_ONLY · FOLD · not a governed keeper. Council/legal integration remains unadmitted; this link grants no action or model authority."))
    else:
        cards = [node("article", node("h3", "Ownership binding unavailable"),
                      node("p", "The bundled public contract could not be admitted. No inventory, owner or Ayllu capability is inferred."), class_="link-card")]
    return node("section", _head("00 · Ownership", "One product. Explicit owners.", "Python-rendered core UI"),
        node("p", "Python owns this page's components. Existing browser interactions still use the retained JavaScript client. This migration does not authorize execution or establish full production readiness.", class_="muted"),
        node("div", *cards, class_="link-grid", id="ownership-links"),
        node("dl", node("div", node("dt", "Public binding"), node("dd", estate.get("state", "UNAVAILABLE"))),
             node("div", node("dt", "Contract SHA-256"), node("dd", node("code", estate.get("sha256") or "UNAVAILABLE"))),
             node("div", node("dt", "Authority"), node("dd", "Public effectors disabled; production authorization is not granted.")),
             class_="binding-evidence"), id="ownership")


def _status(model):
    revision = model.get("source_revision")
    if revision is not None and (not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{40}", revision)):
        raise ValueError("invalid source revision")
    cards = [node("article", node("p", "Python source", class_="eyebrow"),
                  node("p", "Declared by this process · not independently verified" if revision else "Not observed yet", id="source-state"),
                  node("code", revision or "—", id="source-sha"),
                  node("a", "Canonical GitHub ↗", href="https://github.com/szl-holdings/a11oy"))]
    for title, prefix, detail in (
        ("Grok connection", "grok", "Configuration is not successful inference."),
        ("Local open-weight model", "local", "No provider key; this lane is available only from a configured local runtime."),
        ("Public CPU demonstration", "cpu", "Separate SZL Khipu lab; public data only and upstream execution records are unsigned."),
        ("HF inventory", "inventory", "Public snapshot, not qualification."),
    ):
        cards.append(node("article", node("p", title, class_="eyebrow"),
                          node("p", "Not observed yet", id=prefix + "-state"),
                          node("small", detail, id=prefix + "-detail")))
    return node("section", *cards, class_="status-grid", aria_label="Observed runtime status")


def _credential(prefix, local=False):
    key = prefix + "operator-key"
    return (
        node("label", "Local Atelier operator credential" if local else "Atelier operator credential", for_=key),
        node("div", node("input", id=key, type="password", autocomplete="off", spellcheck="false",
                         placeholder="Local operator credential" if local else "Atelier operator credential, not a provider key"),
             node("button", "Forget", id=prefix + "forget-key", type="button", class_="secondary"), class_="key-row"),
        node("small", "Held only in this page’s memory; never saved to browser storage. The provider key stays on the server."),
    )


def _classification(prefix):
    return node("label", "Data classification", node("select", *(node("option", value) for value in ("PUBLIC", "INTERNAL", "RESTRICTED", "SECRET")), id=prefix + "classification"))


def _outcome(prefix, status, label, summary):
    return (
        node("p", status, id=prefix + "turn-status", role="status", aria_live="polite"),
        node("div", id=prefix + "answer", class_="answer", aria_label=label, hidden=True),
        node("details", node("summary", summary), node("pre", id=prefix + "receipt"), id=prefix + "receipt-panel", hidden=True),
    )


def _grok_work():
    return node("section", _head("01 · Work", "Think with Atelier.", "External provider · bounded single turn"),
        node("p", "Grok 4.7 supplies text. SZL controls authentication, policy checks and signed receipts. No tools run here. Atelier's receipt ledger keeps metadata and content-derived hashes, not prompt or answer text; hashes are not anonymization. ",
             node("code", "store: false"), " disables xAI's stateful history; xAI's separate API audit retention is 30 days by default unless the team has Zero Data Retention.", class_="muted"),
        node("form", *_credential(""), node("label", "What are we working on?", for_="prompt"),
             node("textarea", id="prompt", rows="6", maxlength="32000", required=True, placeholder="Describe one task or ask one question. Do not include secrets or restricted information."),
             node("div", node("label", "Model", node("select", node("option", "Grok 4.7", value="grok-4.7"), node("option", "Grok 4.6 · explicit rollback", value="grok-4.6"), id="model")),
                  node("label", "Reasoning", node("select", *(node("option", effort, selected=effort == "high") for effort in ("low", "medium", "high", "xhigh")), id="effort")),
                  _classification(""), node("button", "Send governed request", id="send", type="submit", disabled=True), class_="controls"), id="turn-form"),
        *_outcome("", "No request has been sent. Restricted and secret data cannot leave for Grok.", "Final assistant answer", "Inspect outcome and receipt"),
        node("p", "No automatic retries. A timeout can leave provider execution uncertain; check the outcome before sending another request. Encrypted provider reasoning is not displayed or replayed. Energy is UNAVAILABLE without a measured exporter delta.", class_="fine"), id="work", class_="work panel")


def _local_work():
    return node("section", _head("01 · Work · local", "Think on this computer.", "Open weights · no provider API key"),
        node("p", "A separately configured loopback runtime can use an installed Ollama model without an xAI key. This is not Grok. The public website cannot reach your workstation; this form stays disabled unless its own server reports local configuration ready. The operator credential, policy gate, persistent signer and receipt ledger are still required. Model text is advisory and runs no tools.", class_="muted"),
        node("form", *_credential("local-", local=True), node("label", "What are we working on locally?", for_="local-prompt"),
             node("textarea", id="local-prompt", rows="6", maxlength="32000", required=True, placeholder="Describe one task or ask one question. Do not include secrets or restricted information."),
             node("div", node("label", "Configured model", node("input", id="local-model", type="text", value="Not configured", readonly=True)),
                  _classification("local-"), node("button", "Send local request", id="local-send", type="submit", disabled=True), class_="controls local-controls"), id="local-turn-form"),
        *_outcome("local-", "No local request has been sent.", "Local model answer", "Inspect local outcome and receipt"),
        node("p", "No automatic retries. Local output is not proof of model quality, factual accuracy or action authority. Configuration readiness is not a successful inference; a completed, signed turn is separate evidence.", class_="fine"), id="local-work", class_="work panel local-work")


def _cpu_work():
    return node("section", _head("01 · Work · public demonstration", "Try the SZL CPU lab.", "No provider API key · 32-token ceiling"),
        node("p", "This is a separate, best-effort SZL Khipu 1.5B demonstration, not Grok and not the local Ollama model. Send ", node("strong", "public, non-sensitive text only"),
             "; do not include personal, regulated or secret data. Atelier still requires its operator credential and policy gate, and signs its own decision and observed outcome. The lab's execution record is ", node("strong", "UNSIGNED"),
             ", and a signed Atelier receipt does not prove the lab's answer is correct or its remote execution independently attested. The lab permits one concurrent request and may be unavailable.", class_="muted"),
        node("form", *_credential("cpu-"), node("label", "Public question for the CPU lab", for_="cpu-prompt"),
             node("textarea", id="cpu-prompt", rows="4", maxlength="1200", required=True, placeholder="Ask one short public question. No sensitive information."),
             node("label", node("input", id="cpu-public-ack", type="checkbox", required=True), " I confirm this exact prompt is safe to disclose to the public SZL CPU lab. Automated checks cannot reliably detect all personal, confidential or secret data.", class_="cpu-public-ack"),
             node("div", node("label", "Fixed model", node("input", id="cpu-model", type="text", value="Not configured", readonly=True)),
                  node("label", "Classification", node("input", type="text", value="PUBLIC only", readonly=True)),
                  node("button", "Send bounded demo request", id="cpu-send", type="submit", disabled=True), class_="controls cpu-controls"), id="cpu-turn-form"),
        *_outcome("cpu-", "No CPU lab request has been sent.", "CPU lab model answer", "Inspect Atelier outcome and unsigned lab record hash"),
        node("p", "One request, no automatic retry or tool execution. A timeout can leave the lab outcome uncertain. The upstream lab is a best-effort public demo without an SLA; ", node("a", "inspect its independent source and limits", href="https://huggingface.co/spaces/SZLHOLDINGS/szl-model-inference-lab"), ".", class_="fine"), id="cpu-work", class_="work panel cpu-work")


def _study():
    return node("section", _head("05 · Study", "Study widely. Build independently.", "Research intake · not deployment admission"),
        node("p", "Research snapshot not observed yet.", id="study-summary", class_="muted"),
        node("div", id="study-models", class_="link-grid"),
        node("p", "Popularity is not quality. Provider listings are not successful inference. Declared card licenses still need version-specific review. We study cited public work, implement our own interfaces and mathematics, and require held-out evidence before claiming an improvement. Muse identity remains unconfirmed; Jev is advisory, never permission to act.", class_="fine"),
        node("a", "Inspect the full pinned intake and evaluation protocol ↗", href="/api/a11oy/v1/command-centre/study"),
        node("h3", "2026-10-02 · no-key open-weight shortlist"),
        node("div", _link_card("Qwen3.5-4B · 8 GB study target", "https://huggingface.co/Qwen/Qwen3.5-4B/tree/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a", "Apache-2.0 card · exact Hub revision · not downloaded or qualified here"),
             _link_card("Qwen3.5-9B · 16 GB study target", "https://huggingface.co/Qwen/Qwen3.5-9B/tree/c202236235762e1c871ad0ccb60c8ee5ba337b9a", "Apache-2.0 card · exact Hub revision · not downloaded or qualified here"), class_="link-grid"),
        node("p", "The installed local qwen3:4b-instruct is a separate Ollama artifact. We do not claim it is byte-derived from either Hub checkpoint, and local inference alone does not prove superiority.", class_="fine"), id="study")


def render_page(model):
    """Render exact bytes from a bounded public presentation model; no I/O."""
    if not isinstance(model, dict) or model.get("schema") != "szl.command-centre/v1":
        raise ValueError("invalid page model")
    encoded = json.dumps(model, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(encoded) > 65536:
        raise ValueError("page model exceeds bound")
    input_digest = hashlib.sha256(encoded).hexdigest()
    body = node("html", node("head", node("meta", charset="utf-8"),
        node("meta", name="viewport", content="width=device-width, initial-scale=1"),
        node("title", "SZL Atelier · Command centre"),
        node("meta", name="description", content="One product entry point for governed work, existing SZL runtime tools, canonical source and publication evidence."),
        node("link", rel="canonical", href="https://a-11-oy.com/command-centre"),
        *(node("link", rel="stylesheet", href=path) for path in ("/command-centre/szl/szl-design-system.css", "/command-centre/szl/szl-console.css", "/command-centre/style.css")),
        node("script", src="/command-centre/app.js", defer=True)),
        node("body", node("a", "Skip to work", href="#work", class_="skip"),
            node("div", node("aside", node("a", "SZL", node("span", "Atelier"), href="/", class_="identity"),
                node("p", "Command centre", class_="eyebrow"),
                node("nav", *(node("a", label, href="#" + anchor) for anchor, label in (("ownership", "00 · Ownership"), ("work", "01 · Work"), ("operate", "02 · Operate"), ("verify", "03 · Verify"), ("artifacts", "04 · Artifacts"), ("study", "05 · Study"))), aria_label="Command centre"),
                node("div", node("p", "One fabric. Explicit authorities."), node("a", "Open proof room ↗", href="https://a11oy.net"), class_="rail-foot"), class_="rail"),
                node("main", node("header", node("div", node("p", "a-11-oy.com · operator workspace", class_="eyebrow"), node("h1", "Your work. One centre."), node("p", "Governed conversation, existing tools, and the evidence behind them.", class_="lede")), node("button", "Refresh status", id="refresh", class_="secondary", type="button"), class_="masthead"),
                    node("noscript", "Ownership and navigation are rendered by Python. Interactive status refresh and the existing governed forms require JavaScript; no request is sent without it."),
                    _status(model), _ownership(model), _grok_work(), _local_work(), _cpu_work(),
                    node("section", _head("02 · Operate", "Existing tools, connected.", "Navigation is not action authorization"), node("div", *_links(model, "operate"), id="operate-links", class_="link-grid"), id="operate"),
                    node("section", _head("03 · Verify", "Follow the source."), node("ol", *(node("li", label) for label in ("Protected GitHub Python source", "Canonical Hugging Face publication", "Product and proof verification")), class_="release-order"), node("div", *_links(model, "verify"), id="verify-links", class_="link-grid"), node("p", "The source reported by this process must be checked against protected GitHub main and the publisher’s byte-attestation receipt. A running Space or HTTP 200 does not prove inference.", class_="fine"), id="verify"),
                    node("section", _head("04 · Artifacts", "The SZL estate."), node("div", *_links(model, "artifacts"), id="artifact-links", class_="link-grid"), node("p", "Existing models, kernels, Spaces and datasets keep their own source bindings. This integration creates no SZL-owned Grok weights or training dataset.", class_="fine"), id="artifacts"),
                    _study(), node("footer", node("p", "Doctrine v11 · 8 locked-proven formulas · Λ is Conjecture 1, advisory."), node("a", "Model walk", href="/atelier"), " · ", node("a", "Research workbench", href="/atelier/frontier"), " · ", node("a", "Proof room", href="https://a11oy.net"), node("p", "Python renderer input SHA-256: ", node("code", input_digest), class_="render-provenance")),
                    data_view_input_sha256=input_digest), class_="shell")), lang="en")
    return ("<!doctype html>\n" + body.render() + "\n").encode("utf-8")
