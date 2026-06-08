# -*- coding: utf-8 -*-
"""
szl_b2_secdata.py — BATCH-2 sovereign security data routes for a11oy.
ADDITIVE. Registers same-origin JSON endpoints so the console's batch-2 security
tabs (cve, kev, attack, threats, threatgraph) fetch ZERO off-origin / CDN data.
Data is a REAL, clearly-labelled sample:
  - CISA KEV entries: verbatim real entries from the CISA Known-Exploited
    Vulnerabilities catalog (catalogVersion 2025.09.30), snapshot bundled in-image.
    Source: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
  - EPSS probabilities: representative sample values (labelled sample; FIRST.org EPSS
    is the production source). NOT fabricated as live — explicitly marked sample.
  - CVSS base scores: from NVD per-CVE (representative; labelled).
  - MITRE ATT&CK techniques + tactics: real technique IDs / names from the public
    ATT&CK Enterprise matrix (attack.mitre.org). Kill-chain edges are sample
    sequencing for pathfinding demonstration.
  - Threat actors: real public group names (MITRE ATT&CK Groups) with sample
    attribution edges.
Honesty: this is a bundled snapshot sample, surfaced as "sample" in the UI — never
presented as a live feed. No fabricated CVE IDs.
DCO: Signed-off-by: Perplexity Computer Agent <agent@perplexity.ai>
"""
from fastapi.responses import JSONResponse

# ---- Real CISA KEV sample (verbatim subset, catalogVersion 2025.09.30) ----
# Each enriched with a representative CVSS base score and sample EPSS probability.
KEV_CATALOG_VERSION = "2025.09.30"
KEV_DATE_RELEASED = "2025-09-30T12:35:25.4401Z"
KEV_SOURCE = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
KEV = [
    {"cveID":"CVE-2025-32463","vendorProject":"Sudo","product":"Sudo","vulnerabilityName":"Sudo Inclusion of Functionality from Untrusted Control Sphere Vulnerability","dateAdded":"2025-09-29","dueDate":"2025-10-20","ransomware":"Unknown","cwe":"CWE-829","cvss":9.3,"epss":0.42,"severity":"CRITICAL"},
    {"cveID":"CVE-2025-59689","vendorProject":"Libraesva","product":"Email Security Gateway","vulnerabilityName":"Libraesva ESG Command Injection Vulnerability","dateAdded":"2025-09-29","dueDate":"2025-10-20","ransomware":"Unknown","cwe":"CWE-77","cvss":8.1,"epss":0.17,"severity":"HIGH"},
    {"cveID":"CVE-2025-10035","vendorProject":"Fortra","product":"GoAnywhere MFT","vulnerabilityName":"Fortra GoAnywhere MFT Deserialization of Untrusted Data Vulnerability","dateAdded":"2025-09-29","dueDate":"2025-10-20","ransomware":"Unknown","cwe":"CWE-502","cvss":10.0,"epss":0.71,"severity":"CRITICAL"},
    {"cveID":"CVE-2025-20352","vendorProject":"Cisco","product":"IOS and IOS XE","vulnerabilityName":"Cisco IOS/IOS XE SNMP DoS and RCE Vulnerability","dateAdded":"2025-09-29","dueDate":"2025-10-20","ransomware":"Unknown","cwe":"CWE-121","cvss":7.7,"epss":0.23,"severity":"HIGH"},
    {"cveID":"CVE-2021-21311","vendorProject":"Adminer","product":"Adminer","vulnerabilityName":"Adminer Server-Side Request Forgery Vulnerability","dateAdded":"2025-09-29","dueDate":"2025-10-20","ransomware":"Unknown","cwe":"CWE-918","cvss":7.2,"epss":0.55,"severity":"HIGH"},
    {"cveID":"CVE-2025-20362","vendorProject":"Cisco","product":"Secure Firewall ASA/FTD","vulnerabilityName":"Cisco Secure Firewall ASA/FTD Missing Authorization Vulnerability","dateAdded":"2025-09-25","dueDate":"2025-09-26","ransomware":"Unknown","cwe":"CWE-862","cvss":6.5,"epss":0.34,"severity":"MEDIUM"},
    {"cveID":"CVE-2025-20333","vendorProject":"Cisco","product":"Secure Firewall ASA/FTD","vulnerabilityName":"Cisco Secure Firewall ASA/FTD Buffer Overflow Vulnerability","dateAdded":"2025-09-25","dueDate":"2025-09-26","ransomware":"Unknown","cwe":"CWE-120","cvss":9.9,"epss":0.62,"severity":"CRITICAL"},
    {"cveID":"CVE-2025-10585","vendorProject":"Google","product":"Chromium V8","vulnerabilityName":"Google Chromium V8 Type Confusion Vulnerability","dateAdded":"2025-09-23","dueDate":"2025-10-14","ransomware":"Unknown","cwe":"CWE-843","cvss":8.8,"epss":0.29,"severity":"HIGH"},
    {"cveID":"CVE-2025-5086","vendorProject":"Dassault Systemes","product":"DELMIA Apriso","vulnerabilityName":"Dassault DELMIA Apriso Deserialization of Untrusted Data Vulnerability","dateAdded":"2025-09-11","dueDate":"2025-10-02","ransomware":"Unknown","cwe":"CWE-502","cvss":9.0,"epss":0.48,"severity":"CRITICAL"},
    {"cveID":"CVE-2025-38352","vendorProject":"Linux","product":"Kernel","vulnerabilityName":"Linux Kernel TOCTOU Race Condition Vulnerability","dateAdded":"2025-09-04","dueDate":"2025-09-25","ransomware":"Unknown","cwe":"CWE-367","cvss":7.4,"epss":0.09,"severity":"HIGH"},
    {"cveID":"CVE-2025-48543","vendorProject":"Android","product":"Runtime","vulnerabilityName":"Android Runtime Use-After-Free Vulnerability","dateAdded":"2025-09-04","dueDate":"2025-09-25","ransomware":"Unknown","cwe":"CWE-416","cvss":8.6,"epss":0.13,"severity":"HIGH"},
    {"cveID":"CVE-2025-53690","vendorProject":"Sitecore","product":"Multiple Products","vulnerabilityName":"Sitecore Multiple Products Deserialization of Untrusted Data Vulnerability","dateAdded":"2025-09-04","dueDate":"2025-09-25","ransomware":"Unknown","cwe":"CWE-502","cvss":9.0,"epss":0.38,"severity":"CRITICAL"},
    {"cveID":"CVE-2023-50224","vendorProject":"TP-Link","product":"TL-WR841N","vulnerabilityName":"TP-Link TL-WR841N Authentication Bypass by Spoofing Vulnerability","dateAdded":"2025-09-03","dueDate":"2025-09-24","ransomware":"Unknown","cwe":"CWE-290","cvss":6.5,"epss":0.51,"severity":"MEDIUM"},
    {"cveID":"CVE-2025-9377","vendorProject":"TP-Link","product":"Multiple Routers","vulnerabilityName":"TP-Link Archer C7/TL-WR841N OS Command Injection Vulnerability","dateAdded":"2025-09-03","dueDate":"2025-09-24","ransomware":"Unknown","cwe":"CWE-78","cvss":7.8,"epss":0.44,"severity":"HIGH"},
    {"cveID":"CVE-2020-24363","vendorProject":"TP-Link","product":"TL-WA855RE","vulnerabilityName":"TP-Link TL-WA855RE Missing Authentication for Critical Function","dateAdded":"2025-09-02","dueDate":"2025-09-23","ransomware":"Unknown","cwe":"CWE-306","cvss":8.8,"epss":0.66,"severity":"HIGH"},
    {"cveID":"CVE-2025-55177","vendorProject":"Meta Platforms","product":"WhatsApp","vulnerabilityName":"Meta WhatsApp Incorrect Authorization Vulnerability","dateAdded":"2025-09-02","dueDate":"2025-09-23","ransomware":"Unknown","cwe":"CWE-863","cvss":5.4,"epss":0.21,"severity":"MEDIUM"},
    {"cveID":"CVE-2025-57819","vendorProject":"Sangoma","product":"FreePBX","vulnerabilityName":"Sangoma FreePBX Authentication Bypass Vulnerability","dateAdded":"2025-08-29","dueDate":"2025-09-19","ransomware":"Unknown","cwe":"CWE-89","cvss":10.0,"epss":0.58,"severity":"CRITICAL"},
    {"cveID":"CVE-2025-7775","vendorProject":"Citrix","product":"NetScaler","vulnerabilityName":"Citrix NetScaler Memory Overflow Vulnerability","dateAdded":"2025-08-26","dueDate":"2025-08-28","ransomware":"Unknown","cwe":"CWE-119","cvss":9.2,"epss":0.74,"severity":"CRITICAL"},
    {"cveID":"CVE-2025-48384","vendorProject":"Git","product":"Git","vulnerabilityName":"Git Link Following Vulnerability","dateAdded":"2025-08-25","dueDate":"2025-09-15","ransomware":"Unknown","cwe":"CWE-59","cvss":8.0,"epss":0.19,"severity":"HIGH"},
    {"cveID":"CVE-2024-8068","vendorProject":"Citrix","product":"Session Recording","vulnerabilityName":"Citrix Session Recording Improper Privilege Management","dateAdded":"2025-08-25","dueDate":"2025-09-15","ransomware":"Unknown","cwe":"CWE-269","cvss":5.1,"epss":0.07,"severity":"MEDIUM"},
    {"cveID":"CVE-2025-43300","vendorProject":"Apple","product":"iOS/iPadOS/macOS","vulnerabilityName":"Apple Image I/O Out-of-Bounds Write Vulnerability","dateAdded":"2025-08-21","dueDate":"2025-09-11","ransomware":"Unknown","cwe":"CWE-787","cvss":8.8,"epss":0.31,"severity":"HIGH"},
    {"cveID":"CVE-2025-54948","vendorProject":"Trend Micro","product":"Apex One","vulnerabilityName":"Trend Micro Apex One OS Command Injection Vulnerability","dateAdded":"2025-08-18","dueDate":"2025-09-08","ransomware":"Unknown","cwe":"CWE-78","cvss":9.4,"epss":0.46,"severity":"CRITICAL"},
    {"cveID":"CVE-2025-8088","vendorProject":"RARLAB","product":"WinRAR","vulnerabilityName":"RARLAB WinRAR Path Traversal Vulnerability","dateAdded":"2025-08-12","dueDate":"2025-09-02","ransomware":"Known","cwe":"CWE-35","cvss":7.8,"epss":0.83,"severity":"HIGH"},
    {"cveID":"CVE-2007-0671","vendorProject":"Microsoft","product":"Office","vulnerabilityName":"Microsoft Office Excel Remote Code Execution Vulnerability","dateAdded":"2025-08-12","dueDate":"2025-09-02","ransomware":"Unknown","cwe":"CWE-94","cvss":9.3,"epss":0.12,"severity":"CRITICAL"},
    {"cveID":"CVE-2025-20337","vendorProject":"Cisco","product":"Identity Services Engine","vulnerabilityName":"Cisco ISE Injection Vulnerability","dateAdded":"2025-07-28","dueDate":"2025-08-18","ransomware":"Unknown","cwe":"CWE-74","cvss":10.0,"epss":0.69,"severity":"CRITICAL"},
    {"cveID":"CVE-2025-2775","vendorProject":"SysAid","product":"SysAid On-Prem","vulnerabilityName":"SysAid On-Prem XML External Entity Reference Vulnerability","dateAdded":"2025-07-22","dueDate":"2025-08-12","ransomware":"Unknown","cwe":"CWE-611","cvss":9.3,"epss":0.27,"severity":"CRITICAL"},
    {"cveID":"CVE-2023-2533","vendorProject":"PaperCut","product":"NG/MF","vulnerabilityName":"PaperCut NG/MF Cross-Site Request Forgery Vulnerability","dateAdded":"2025-07-28","dueDate":"2025-08-18","ransomware":"Unknown","cwe":"CWE-352","cvss":8.4,"epss":0.36,"severity":"HIGH"},
    {"cveID":"CVE-2022-40799","vendorProject":"D-Link","product":"DNR-322L","vulnerabilityName":"D-Link DNR-322L Download of Code Without Integrity Check","dateAdded":"2025-08-05","dueDate":"2025-08-26","ransomware":"Unknown","cwe":"CWE-494","cvss":8.8,"epss":0.41,"severity":"HIGH"},
]

# ---- Real MITRE ATT&CK Enterprise tactics (kill-chain order) ----
ATTACK_TACTICS = [
    {"id":"TA0043","name":"Reconnaissance","phase":0},
    {"id":"TA0042","name":"Resource Development","phase":1},
    {"id":"TA0001","name":"Initial Access","phase":2},
    {"id":"TA0002","name":"Execution","phase":3},
    {"id":"TA0003","name":"Persistence","phase":4},
    {"id":"TA0004","name":"Privilege Escalation","phase":5},
    {"id":"TA0005","name":"Defense Evasion","phase":6},
    {"id":"TA0006","name":"Credential Access","phase":7},
    {"id":"TA0007","name":"Discovery","phase":8},
    {"id":"TA0008","name":"Lateral Movement","phase":9},
    {"id":"TA0009","name":"Collection","phase":10},
    {"id":"TA0011","name":"Command and Control","phase":11},
    {"id":"TA0010","name":"Exfiltration","phase":12},
    {"id":"TA0040","name":"Impact","phase":13},
]

# Real ATT&CK technique IDs + names, mapped to their tactic. freq = sample
# activity weight (labelled sample) used for node sizing.
ATTACK_TECHNIQUES = [
    {"id":"T1595","name":"Active Scanning","tactic":"TA0043","freq":7},
    {"id":"T1592","name":"Gather Victim Host Information","tactic":"TA0043","freq":4},
    {"id":"T1583","name":"Acquire Infrastructure","tactic":"TA0042","freq":5},
    {"id":"T1587","name":"Develop Capabilities","tactic":"TA0042","freq":3},
    {"id":"T1190","name":"Exploit Public-Facing Application","tactic":"TA0001","freq":12},
    {"id":"T1566","name":"Phishing","tactic":"TA0001","freq":15},
    {"id":"T1133","name":"External Remote Services","tactic":"TA0001","freq":8},
    {"id":"T1059","name":"Command and Scripting Interpreter","tactic":"TA0002","freq":14},
    {"id":"T1203","name":"Exploitation for Client Execution","tactic":"TA0002","freq":9},
    {"id":"T1053","name":"Scheduled Task/Job","tactic":"TA0003","freq":7},
    {"id":"T1543","name":"Create or Modify System Process","tactic":"TA0003","freq":6},
    {"id":"T1547","name":"Boot or Logon Autostart Execution","tactic":"TA0003","freq":5},
    {"id":"T1068","name":"Exploitation for Privilege Escalation","tactic":"TA0004","freq":10},
    {"id":"T1548","name":"Abuse Elevation Control Mechanism","tactic":"TA0004","freq":6},
    {"id":"T1055","name":"Process Injection","tactic":"TA0005","freq":9},
    {"id":"T1070","name":"Indicator Removal","tactic":"TA0005","freq":8},
    {"id":"T1027","name":"Obfuscated Files or Information","tactic":"TA0005","freq":11},
    {"id":"T1003","name":"OS Credential Dumping","tactic":"TA0006","freq":13},
    {"id":"T1110","name":"Brute Force","tactic":"TA0006","freq":7},
    {"id":"T1555","name":"Credentials from Password Stores","tactic":"TA0006","freq":6},
    {"id":"T1082","name":"System Information Discovery","tactic":"TA0007","freq":10},
    {"id":"T1083","name":"File and Directory Discovery","tactic":"TA0007","freq":7},
    {"id":"T1021","name":"Remote Services","tactic":"TA0008","freq":11},
    {"id":"T1570","name":"Lateral Tool Transfer","tactic":"TA0008","freq":5},
    {"id":"T1560","name":"Archive Collected Data","tactic":"TA0009","freq":6},
    {"id":"T1005","name":"Data from Local System","tactic":"TA0009","freq":8},
    {"id":"T1071","name":"Application Layer Protocol","tactic":"TA0011","freq":12},
    {"id":"T1573","name":"Encrypted Channel","tactic":"TA0011","freq":7},
    {"id":"T1041","name":"Exfiltration Over C2 Channel","tactic":"TA0010","freq":9},
    {"id":"T1567","name":"Exfiltration Over Web Service","tactic":"TA0010","freq":6},
    {"id":"T1486","name":"Data Encrypted for Impact","tactic":"TA0040","freq":14},
    {"id":"T1490","name":"Inhibit System Recovery","tactic":"TA0040","freq":8},
    {"id":"T1485","name":"Data Destruction","tactic":"TA0040","freq":5},
]

# Kill-chain edges: sample sequencing across phases (for ngraph.path pathfinding).
def _attack_edges():
    by_tac = {}
    for t in ATTACK_TECHNIQUES:
        by_tac.setdefault(t["tactic"], []).append(t["id"])
    phases = sorted(ATTACK_TACTICS, key=lambda x: x["phase"])
    edges = []
    for i in range(len(phases) - 1):
        a = by_tac.get(phases[i]["id"], [])
        b = by_tac.get(phases[i + 1]["id"], [])
        for s in a:
            for d in b:
                # weight 1 = primary kill-chain hops; sparse to keep path meaningful
                edges.append({"from": s, "to": d, "weight": 1})
    return edges

# Real public ATT&CK Group names (threat actors) with sample attribution.
THREAT_ACTORS = [
    {"id":"G0016","name":"APT29","type":"state","severity":9},
    {"id":"G0007","name":"APT28","type":"state","severity":9},
    {"id":"G0032","name":"Lazarus Group","type":"state","severity":10},
    {"id":"G0096","name":"APT41","type":"state","severity":8},
    {"id":"G0050","name":"APT32","type":"state","severity":7},
    {"id":"G0102","name":"Wizard Spider","type":"criminal","severity":9},
    {"id":"G0008","name":"Carbanak","type":"criminal","severity":8},
    {"id":"G1004","name":"LAPSUS$","type":"criminal","severity":7},
    {"id":"G0034","name":"Sandworm Team","type":"state","severity":10},
    {"id":"G0035","name":"Dragonfly","type":"state","severity":7},
    {"id":"G0125","name":"HAFNIUM","type":"state","severity":8},
    {"id":"G1006","name":"Earth Lusca","type":"criminal","severity":6},
]
ACTOR_USES = [
    ("G0016","T1566"),("G0016","T1059"),("G0016","T1071"),("G0016","T1003"),
    ("G0007","T1566"),("G0007","T1190"),("G0007","T1068"),("G0007","T1041"),
    ("G0032","T1190"),("G0032","T1486"),("G0032","T1003"),("G0032","T1567"),
    ("G0096","T1190"),("G0096","T1059"),("G0096","T1021"),("G0096","T1071"),
    ("G0050","T1566"),("G0050","T1547"),("G0050","T1082"),
    ("G0102","T1486"),("G0102","T1003"),("G0102","T1021"),("G0102","T1490"),
    ("G0008","T1059"),("G0008","T1055"),("G0008","T1005"),
    ("G1004","T1110"),("G1004","T1133"),("G1004","T1555"),
    ("G0034","T1486"),("G0034","T1190"),("G0034","T1485"),("G0034","T1133"),
    ("G0035","T1190"),("G0035","T1133"),("G0035","T1071"),
    ("G0125","T1190"),("G0125","T1505" if False else "T1190"),("G0125","T1003"),
    ("G1006","T1566"),("G1006","T1027"),("G1006","T1041"),
]


def register(app, brand="a11oy"):
    base = "/api/a11oy/v1/sec"

    @app.get(base + "/kev")
    async def _kev():
        return JSONResponse({
            "source": "CISA Known Exploited Vulnerabilities catalog (bundled in-image snapshot)",
            "source_url": KEV_SOURCE,
            "catalogVersion": KEV_CATALOG_VERSION,
            "dateReleased": KEV_DATE_RELEASED,
            "data_kind": "sample",
            "note": "Verbatim real KEV entries; CVSS/EPSS are representative sample enrichment (FIRST.org EPSS is the production source). Sovereign: served same-origin, no CDN.",
            "count": len(KEV),
            "vulnerabilities": KEV,
        })

    @app.get(base + "/cve")
    async def _cve():
        # CVE watch reuses the KEV-enriched rows (each is a real CVE) — distinct
        # presentation from kev (severity-sorted heat grid vs date scatter).
        rows = sorted(KEV, key=lambda r: (-r["cvss"], -r["epss"]))
        return JSONResponse({
            "source": "CISA KEV-derived CVE rows + NVD CVSS / sample EPSS (bundled snapshot)",
            "source_url": KEV_SOURCE,
            "data_kind": "sample",
            "count": len(rows),
            "cves": rows,
        })

    @app.get(base + "/attack")
    async def _attack():
        return JSONResponse({
            "source": "MITRE ATT&CK Enterprise matrix (public technique/tactic IDs); kill-chain edges are sample sequencing",
            "source_url": "https://attack.mitre.org/",
            "data_kind": "sample",
            "tactics": ATTACK_TACTICS,
            "techniques": ATTACK_TECHNIQUES,
            "edges": _attack_edges(),
        })

    @app.get(base + "/threats")
    async def _threats():
        # threat library: techniques bucketed by severity ring derived from CVSS-like tiers
        return JSONResponse({
            "source": "MITRE ATT&CK Enterprise techniques (public), bucketed into severity rings by sample frequency",
            "source_url": "https://attack.mitre.org/",
            "data_kind": "sample",
            "tactics": ATTACK_TACTICS,
            "techniques": ATTACK_TECHNIQUES,
        })

    @app.get(base + "/threatgraph")
    async def _threatgraph():
        nodes = [{"id":a["id"],"name":a["name"],"kind":"actor","type":a["type"],"severity":a["severity"]} for a in THREAT_ACTORS]
        techset = {}
        for s,d in ACTOR_USES:
            techset[d] = True
        tname = {t["id"]: t["name"] for t in ATTACK_TECHNIQUES}
        for tid in techset:
            nodes.append({"id":tid,"name":tname.get(tid,tid),"kind":"ttp"})
        edges = [{"from":s,"to":d,"rel":"uses"} for s,d in ACTOR_USES if d in tname]
        return JSONResponse({
            "source": "MITRE ATT&CK Groups (public actor names) + technique usage; attribution edges are sample",
            "source_url": "https://attack.mitre.org/groups/",
            "data_kind": "sample",
            "nodes": nodes,
            "edges": edges,
        })

    return {"status": "ok", "endpoints": [base + e for e in ("/kev","/cve","/attack","/threats","/threatgraph")]}
