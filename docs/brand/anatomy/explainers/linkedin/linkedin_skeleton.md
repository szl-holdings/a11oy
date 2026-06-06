# LinkedIn post — anatomy_skeleton (THE SKELETON)

---

Most software architecture diagrams show services.

Ours shows bones.

Twelve service repositories. Each one is a named structural element. Some are axial — remove them and the organism collapses. Others are appendicular — removable without killing the system, but posture degrades.

**The axial spine: four load-bearing repos.**

`szl-doctrine` holds the 9-axis conjunctive gate, the HUKLLA tripwire table, and the YAWAR write doctrine. It is the vertebral column. The other three axial repos — `szl-yawar` (the append-only receipt bus), `szl-hatun` (the sovereign RAID loop orchestrator), and `szl-terra` (the React 18 BodyGraph surface) — are the vertebrae that make posture possible.

**The appendicular bones: eight capability repos.**

`szl-brain`, `szl-overwatch`, `szl-wires`, `szl-rimay`, `szl-sentra`, `szl-tupu-t7`, `szl-chakana`, `szl-brand`. Each is a limb or rib. The system walks without them. But it walks with a limp, and the limp is visible in the receipt chain.

**Why twelve, not forty.**

Scope is a structural property. A skeleton with too many bones is a liability: more joints, more failure surfaces, more coordination overhead. Twelve repos means twelve audit targets, twelve deployment surfaces, twelve places where a commit can alter system behavior. That number is deliberate. We track it.

**The skeletal frame is a constraint, not a catalog.**

An architecture diagram lists what exists. The skeleton tells you what the system *requires* to stand. The distinction matters when you are debugging at 2 AM and need to know which repo contains the load path.

**What the diagram shows.**

Axial repos carry a gold border. Appendicular repos in two columns: left (brain, overwatch, wires, rimay) and right (sentra, tupu-t7, chakana, brand). Each card shows language, estimated SLOC, and operational status. Connectors between cards and the central spine represent dependency, not data flow.

Data flow is the nervous system. That is a different diagram.

---

*anatomy_skeleton.pdf — figure 4 of 8 in the SZL agent anatomy series.*
*Lutar, Stephen P. · SZL Holdings · CC-BY-4.0*
