// VENDORED FROM szl-holdings/platform@e87ad75ec8e280e2fe3a3e8f49c5c0b6c2eec4ea — artifacts/sentra/src/data/darpa-mto-research.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
export type ResearchDomain = {
  id: string;
  title: string;
  darpaProgram: string;
  programManager?: string;
  status: 'incubation' | 'active' | 'reference';
  cyberApplication: string;
  description: string;
  keyBreakthroughs: string[];
  topRepos: { name: string; org: string; stars?: string; tech: string }[];
  topPapers: { title: string; venue: string; year: number }[];
  a11oyIntegration: string;
  trl: number;
};

export const DARPA_MTO_DOMAINS: ResearchDomain[] = [
  {
    id: 'photonic-inference',
    title: 'Photonic Reconfigurable Inference',
    darpaProgram: 'PRISM / PIPES / LUMOS',
    programManager: 'Todd Bauer',
    status: 'incubation',
    cyberApplication: 'Ultra-fast AI threat inference at line speed with near-zero power',
    description:
      'Scalable 3D optoelectronic platforms for energy-efficient parallel computation. MIT demonstrated a fully integrated photonic DNN chip achieving 92% inference accuracy in <0.5 nanoseconds. Nature 2025 published a 16,000-component photonic accelerator.',
    keyBreakthroughs: [
      'MIT photonic DNN: 92% accuracy, sub-nanosecond inference (Nature Photonics 2024)',
      'Nature 2025: 16,000-component single-chip photonic accelerator',
      'Lightmatter Passage: commercial photonic interconnect fabric',
      'CMOS-compatible fabrication enabling mass production',
    ],
    topRepos: [
      { name: 'photontorch', org: 'flaport', stars: '400+', tech: 'PyTorch photonic simulation' },
      { name: 'neuroptica', org: 'fancompute', stars: '200+', tech: 'Photonic neural network sim' },
      { name: 'simphony', org: 'BYUCameras', stars: '100+', tech: 'Photonic circuit simulation' },
    ],
    topPapers: [
      { title: 'Single-chip photonic deep neural network with forward-only training', venue: 'Nature Photonics', year: 2024 },
      { title: 'Large-scale photonic accelerator with 16,000+ integrated components', venue: 'Nature', year: 2025 },
    ],
    a11oyIntegration: 'a11oy routes inference workloads to photonic accelerators when available, falling back to GPU/CPU. The Model Router already supports hardware-class routing — photonic becomes a new compute tier for sub-nanosecond threat classification.',
    trl: 4,
  },
  {
    id: 'quantum-resilience',
    title: 'Quantum Superposition & Post-Quantum Cryptography',
    darpaProgram: 'QBI / RoQS / NIST PQC',
    programManager: 'Jonathan Hoffman',
    status: 'active',
    cyberApplication: 'Quantum-resistant key exchange and digital signatures across the agent mesh',
    description:
      'NIST finalized FIPS 203 (ML-KEM/Kyber), FIPS 204 (ML-DSA/Dilithium), and FIPS 205 (SLH-DSA/SPHINCS+) in August 2024. Chrome 131 deployed hybrid X25519MLKEM768 by default. Over 33% of Cloudflare HTTPS traffic uses post-quantum handshakes as of March 2025.',
    keyBreakthroughs: [
      'NIST FIPS 203/204/205 finalized August 2024',
      'Chrome 131: hybrid post-quantum key exchange deployed globally (Nov 2024)',
      '33% of Cloudflare HTTPS traffic uses hybrid PQC handshakes (Mar 2025)',
      '@noble/post-quantum: production-ready TypeScript ML-KEM/ML-DSA (MIT license)',
      'DARPA QBI: 11 companies advanced to Stage B for utility-scale quantum computing',
    ],
    topRepos: [
      { name: 'noble-post-quantum', org: 'paulmillr', stars: '60K+ weekly npm', tech: 'TypeScript ML-KEM, ML-DSA, SLH-DSA' },
      { name: 'mlkem', org: 'dajiaji', stars: 'Active', tech: 'TypeScript FIPS 203 ML-KEM' },
      { name: 'liboqs', org: 'open-quantum-safe', stars: '1.8K+', tech: 'C library for PQC algorithms' },
      { name: 'oqs-provider', org: 'open-quantum-safe', stars: '250+', tech: 'OpenSSL 3 PQC provider' },
    ],
    topPapers: [
      { title: 'FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism Standard', venue: 'NIST', year: 2024 },
      { title: 'FIPS 204: Module-Lattice-Based Digital Signature Standard', venue: 'NIST', year: 2024 },
    ],
    a11oyIntegration: 'The Proof Chain and evidence ledger transition to ML-KEM for key encapsulation and ML-DSA for signature verification. Agent mesh inter-node communication upgrades to hybrid X25519MLKEM768. All covenant attestations become quantum-resistant.',
    trl: 7,
  },
  {
    id: 'skyrmion-memory',
    title: 'Skyrmion-Based Magnetic Memory',
    darpaProgram: 'TEE (Topological Excitations in Electronics)',
    programManager: 'Thomas Schratwieser',
    status: 'active',
    cyberApplication: 'Radiation-hardened, tamper-evident secure memory for hardware roots of trust',
    description:
      'Magnetic skyrmions — topological spin structures 10,000x smaller than a human hair — encode bits with intrinsic radiation and thermal error resistance. DARPA TEE awarded $6.34M to Ohio State CEM. Skyrmions can be moved with extremely low energy currents.',
    keyBreakthroughs: [
      'DARPA TEE: $6.34M to Ohio State for skyrmion materials development',
      'Skyrmions inherently resistant to thermal and radiation-based bit errors',
      'Ultra-dense storage: 10,000x smaller than conventional magnetic domains',
      'Energy-efficient: skyrmions move with minimal current injection',
    ],
    topRepos: [
      { name: 'mumax3', org: 'mumax', stars: '300+', tech: 'GPU-accelerated micromagnetic simulation' },
      { name: 'fidimag', org: 'computationalmodelling', stars: '100+', tech: 'Micromagnetic/atomistic simulation' },
      { name: 'spirit', org: 'spirit-code', stars: '80+', tech: 'Spin dynamics simulation' },
    ],
    topPapers: [
      { title: 'Magnetic skyrmions: advances in physics and applications', venue: 'Nature Reviews Physics', year: 2024 },
    ],
    a11oyIntegration: 'Hardware security modules (HSMs) in the a11oy trust chain can leverage skyrmion-based memory for radiation-hardened key storage. The tamper-evident property maps directly to covenant enforcement — physical evidence of key extraction attempts.',
    trl: 3,
  },
  {
    id: 'circuits-on-demand',
    title: 'Circuits On Demand & Hardware Root of Trust',
    darpaProgram: 'AISS / SAHARA / SSITH / SHIELD',
    programManager: 'Todd Bauer',
    status: 'active',
    cyberApplication: 'Custom security silicon, supply chain integrity verification, hardware-enforced isolation',
    description:
      'DARPA AISS automates secure chip design. SAHARA converts FPGA prototypes to secure ASICs. SSITH creates processor architectures immune to hardware vulnerability classes. SHIELD embeds micro-scale hardware roots of trust. INGOTS targets vulnerability coverage.',
    keyBreakthroughs: [
      'AISS: automated secure silicon design flow (Synopsys, Arm, Boeing)',
      'SSITH: hardware architectures immune to 7 CWE vulnerability classes',
      'SHIELD: micro-scale "dielet" hardware root of trust chips',
      'DARPA Toolbox: open licensing of commercial security IP',
      'CHERI capability-based hardware from SSITH (Arm Morello)',
    ],
    topRepos: [
      { name: 'cheri-clang', org: 'CTSRD-CHERI', stars: '200+', tech: 'CHERI LLVM/Clang compiler' },
      { name: 'sail-cheri-riscv', org: 'CTSRD-CHERI', stars: '50+', tech: 'CHERI RISC-V ISA formal model' },
      { name: 'cheribsd', org: 'CTSRD-CHERI', stars: '300+', tech: 'CHERI-enhanced BSD operating system' },
    ],
    topPapers: [
      { title: 'An Introduction to CHERI', venue: 'University of Cambridge TR', year: 2024 },
      { title: 'SSITH: System Security Integrated Through Hardware and Firmware', venue: 'DARPA', year: 2023 },
    ],
    a11oyIntegration: 'a11oy governance enforces CHERI-style capability compartments in software — each agent workcell runs with least-privilege memory access. Supply chain attestation validates hardware provenance using SHIELD-inspired dielet concepts.',
    trl: 6,
  },
  {
    id: 'nanofluidic-computing',
    title: 'Nanofluidic & Iontronic Computing',
    darpaProgram: 'MTO Incubation',
    programManager: 'Yogendra Joshi',
    status: 'incubation',
    cyberApplication: 'Ultra-low-power anomaly detection at the edge with brain-like energy efficiency',
    description:
      'Bio-inspired nanofluidic circuits emulate the brain\'s ion-channel computation. Aqueous memristors demonstrate synaptic plasticity through ion transport in water. EPFL and LLNL lead foundational research. Power consumption approaches biological systems (~20W for brain-equivalent).',
    keyBreakthroughs: [
      'Aqueous memristors emulating short-term synaptic plasticity (Nature 2024)',
      'EPFL nanofluidic transistors for ionic logic gates',
      'Ion-channel computing for pattern recognition at ~1000x less power',
      'Brain-inspired temporal coding for sequence anomaly detection',
    ],
    topRepos: [
      { name: 'brian2', org: 'brian-team', stars: '900+', tech: 'Neural simulator for spiking networks' },
      { name: 'nengo', org: 'nengo', stars: '800+', tech: 'Brain-inspired computing framework' },
      { name: 'norse', org: 'norse', stars: '700+', tech: 'PyTorch spiking neural networks' },
    ],
    topPapers: [
      { title: 'Aqueous memristors for brain-inspired computing', venue: 'Nature', year: 2024 },
      { title: 'Nanofluidic iontronics: principles and applications', venue: 'Nature Reviews Materials', year: 2024 },
    ],
    a11oyIntegration: 'a11oy\'s edge inference pipeline can leverage neuromorphic computing for always-on anomaly detection. The spiking-network paradigm maps to temporal pattern recognition in network traffic — detecting low-and-slow attacks with near-zero power.',
    trl: 2,
  },
  {
    id: 'optical-comms',
    title: 'All-Weather Optical Communications',
    darpaProgram: 'ORCA / ORCLE / ATOM',
    programManager: 'Thomas Schratwieser',
    status: 'incubation',
    cyberApplication: 'Quantum-secure optical key distribution resistant to atmospheric disruption',
    description:
      'DARPA has invested $130M+ in overcoming free-space optical atmospheric limitations. ATOM seeks tunable optical materials across visible, MWIR, and LWIR spectra. Phase-change materials enable fast optical switching for secure communication channels.',
    keyBreakthroughs: [
      '$130M+ DARPA investment in atmospheric FSO penetration',
      'ATOM: tunable optical materials for multi-spectral operation',
      'Phase-change material switching for reconfigurable optical paths',
      'Turbulence compensation through adaptive optics and ML',
    ],
    topRepos: [
      { name: 'opticspy', org: 'opticspy', stars: '50+', tech: 'Optical system simulation' },
      { name: 'aotools', org: 'AOtools', stars: '100+', tech: 'Adaptive optics simulation toolkit' },
    ],
    topPapers: [
      { title: 'Free-space optical communication through atmospheric turbulence', venue: 'IEEE Photonics', year: 2024 },
    ],
    a11oyIntegration: 'Secure optical links provide a quantum key distribution (QKD) channel between a11oy trust nodes. All-weather operation ensures governance attestations propagate even under adversarial atmospheric conditions — no electronic intercept surface.',
    trl: 4,
  },
  {
    id: '3d-microsystems',
    title: '3D Heterogeneous Integration & Chiplet Security',
    darpaProgram: 'NGMM / SHIP / MEADOW',
    programManager: 'David Meyer',
    status: 'active',
    cyberApplication: 'Secure multi-chiplet architectures with hardware-isolated trust domains',
    description:
      'DARPA NGMM selected Texas Institute for Electronics (TIE) for a $1.4B investment to develop 3D heterogeneous integration. Multi-chiplet systems enable hardware-isolated security domains — each chiplet can enforce its own trust boundary with dedicated crypto engines.',
    keyBreakthroughs: [
      'NGMM: $1.4B investment in 3D heterogeneous integration (TIE, UT Austin)',
      'Chiplet-based architectures enable per-domain hardware trust boundaries',
      'Advanced packaging enables heterogeneous materials integration',
      'Defense-specific chiplets with embedded security monitors',
    ],
    topRepos: [
      { name: 'OpenROAD', org: 'The-OpenROAD-Project', stars: '1.5K+', tech: 'Open-source chip design flow' },
      { name: 'OpenLane', org: 'efabless', stars: '1.2K+', tech: 'Automated RTL-to-GDSII flow' },
    ],
    topPapers: [
      { title: 'Next-Generation Microelectronics Manufacturing (NGMM)', venue: 'DARPA', year: 2024 },
    ],
    a11oyIntegration: 'a11oy\'s compartmentalization model mirrors chiplet trust boundaries in software. Each agent workcell maps to a logical "chiplet" with its own crypto engine, memory isolation, and governance attestation — defense-in-depth at the architecture level.',
    trl: 5,
  },
  {
    id: 'flexoelectric-sensors',
    title: 'Flexoelectric Nanoscale Sensors',
    darpaProgram: 'MTO Incubation (FUNS)',
    programManager: 'David Meyer',
    status: 'incubation',
    cyberApplication: 'Ultra-sensitive tamper detection and side-channel monitoring at nanoscale',
    description:
      'Flexoelectricity generates electric signals from strain gradients — no piezoelectric symmetry constraints. At nanoscale, flexoelectric response exceeds piezoelectric. This enables sensors that detect sub-micron physical tamper attempts and side-channel emanations.',
    keyBreakthroughs: [
      'Flexoelectric effect scales inversely with size — stronger at nanoscale',
      'No Curie temperature limitation unlike piezoelectric materials',
      'Works in all dielectric materials, not just specific crystal structures',
      'Enables distributed tamper-detection meshes on chip packages',
    ],
    topRepos: [
      { name: 'MFEM', org: 'mfem', stars: '1.5K+', tech: 'Finite element methods library' },
    ],
    topPapers: [
      { title: 'Flexoelectricity in solids: progress and perspectives', venue: 'Nano Energy', year: 2024 },
    ],
    a11oyIntegration: 'Hardware trust anchors use flexoelectric sensor meshes to detect physical intrusion. Any attempt to probe, decap, or tamper with a11oy HSMs generates electrical signals that trigger automatic key zeroization and governance alerts.',
    trl: 2,
  },
  {
    id: 'molecular-machines',
    title: 'Sequence-Defined Polymer & Molecular Machines',
    darpaProgram: 'MTO Incubation',
    programManager: 'John M. Hoffman',
    status: 'incubation',
    cyberApplication: 'DNA-based data storage and molecular-scale unclonable authentication tokens',
    description:
      'Molecular machines that synthesize sequence-defined polymers enable programmable matter at the molecular level. Applications include DNA-based archival storage (1 exabyte per gram), physically unclonable functions (PUFs) at molecular scale, and bio-degradable security tokens.',
    keyBreakthroughs: [
      'DNA storage: 1 exabyte per gram, 1000+ year archival stability',
      'Molecular PUFs: physically unclonable at atomic scale',
      'Sequence-programmable: each polymer chain encodes unique identity',
      'Bio-degradable security tokens for one-time-use authentication',
    ],
    topRepos: [
      { name: 'dna-storage', org: 'microsoft', stars: '200+', tech: 'DNA data storage research' },
      { name: 'hedges', org: 'microsoft', stars: '100+', tech: 'DNA error-correcting codec' },
    ],
    topPapers: [
      { title: 'Molecular machines for sequence-defined polymer synthesis', venue: 'Nature Chemistry', year: 2024 },
    ],
    a11oyIntegration: 'Long-term evidence archival uses DNA-inspired encoding for immutable audit trails. Molecular PUFs provide hardware-bound identity tokens for agent attestation — each a11oy agent carries a unique, unclonable molecular identity.',
    trl: 2,
  },
  {
    id: 'directed-energy-systems',
    title: 'Directed Energy & Microsystem Sensing',
    darpaProgram: 'MTO Incubation',
    programManager: 'Huanan Zhang',
    status: 'incubation',
    cyberApplication: 'THz imaging for hardware inspection and electromagnetic fault injection detection',
    description:
      'Directed energy microsystems enable precise electromagnetic sensing. THz imaging can non-destructively inspect IC packages for trojans. EM fault injection detection uses integrated sensors to identify active electromagnetic attacks on computing hardware.',
    keyBreakthroughs: [
      'THz imaging resolution reaching sub-100μm for IC inspection',
      'Real-time EM fault injection detection via integrated sensors',
      'Compact directed-energy sources for field-operable inspection',
      'Multi-modal sensing combining THz, RF, and acoustic channels',
    ],
    topRepos: [
      { name: 'terahertz-imaging', org: 'various', stars: 'Growing', tech: 'THz signal processing' },
    ],
    topPapers: [
      { title: 'Terahertz imaging for semiconductor fault analysis', venue: 'IEEE IRPS', year: 2024 },
    ],
    a11oyIntegration: 'Supply chain attestation includes THz imaging verification of hardware components. a11oy governance surfaces inspection results in the trust provenance chain — every hardware component entering the mesh has an electromagnetic fingerprint on file.',
    trl: 3,
  },
  {
    id: 'bio-apertures',
    title: 'Biological Apertures & Bio-Hybrid Sensing',
    darpaProgram: 'MTO Incubation',
    programManager: 'Daniel Ridge',
    status: 'incubation',
    cyberApplication: 'Bio-hybrid intrusion detection with self-healing sensor networks',
    description:
      'Functional bio-apertures with tunable properties combine biological responsiveness with microsystem precision. Bio-hybrid sensor networks can detect chemical, biological, and electromagnetic anomalies with self-healing and adaptive capabilities.',
    keyBreakthroughs: [
      'Tunable biological membranes responsive to chemical signals',
      'Self-healing sensor networks inspired by biological regeneration',
      'Microsystem-scale bio-hybrid detectors for multi-modal sensing',
      'Adaptive sensitivity tuning based on environmental conditions',
    ],
    topRepos: [
      { name: 'biosensors', org: 'MDPI', stars: 'Journal', tech: 'Bio-sensor research community' },
    ],
    topPapers: [
      { title: 'Bio-hybrid microsystems for environmental sensing', venue: 'Advanced Materials', year: 2024 },
    ],
    a11oyIntegration: 'Conceptual bridge: a11oy\'s agent mesh operates like a bio-hybrid sensor network — each agent adapts sensitivity to its environment, self-heals after compromise, and tunes detection thresholds based on threat context. The biological aperture metaphor drives adaptive defense posture.',
    trl: 1,
  },
  {
    id: 'physical-intelligence',
    title: 'Physical Intelligence in Materials',
    darpaProgram: 'MTO Incubation',
    programManager: 'Julian McMorrow',
    status: 'incubation',
    cyberApplication: 'Self-reconfiguring network topologies and physically adaptive defense systems',
    description:
      'Foundational materials, interfaces, and assembly schemes for soft robotics enable physically adaptive systems. The "physical intelligence" concept — materials that compute through their structure — maps to network topologies that physically reconfigure under threat.',
    keyBreakthroughs: [
      'Multi-functional materials combining sensing, actuation, and computation',
      'Self-reconfiguring architectures that adapt to damage',
      'Morphological computation: structure performs computation',
      'Soft robotic principles applied to resilient infrastructure',
    ],
    topRepos: [
      { name: 'sofa', org: 'sofa-framework', stars: '2K+', tech: 'Soft robotics simulation' },
      { name: 'softrobotics-toolkit', org: 'Harvard', stars: '200+', tech: 'Soft robotics design tools' },
    ],
    topPapers: [
      { title: 'Physical intelligence and soft robotics', venue: 'Science Robotics', year: 2024 },
    ],
    a11oyIntegration: 'a11oy\'s mesh topology implements "morphological defense" — the network structure itself embodies security logic. Under attack, the mesh physically reconfigures: isolating compromised nodes, rerouting trust paths, and adapting its shape to the threat landscape.',
    trl: 2,
  },
  {
    id: 'lunar-supply-chain',
    title: 'Lunar Manufacturing & Extreme Supply Chain',
    darpaProgram: 'MTO Incubation / 10-Year Lunar Architecture',
    programManager: 'Julian McMorrow',
    status: 'incubation',
    cyberApplication: 'Zero-trust supply chains for disconnected, high-latency, adversarial environments',
    description:
      'Lunar ISRU requires manufacturing in extremely constrained, disconnected environments with multi-second communication latency. The supply chain security model for lunar operations maps directly to air-gapped networks, satellite constellations, and austere edge deployments.',
    keyBreakthroughs: [
      'DARPA 10-Year Lunar Architecture study for sustained operations',
      'In-situ resource utilization requiring autonomous quality assurance',
      'Multi-second latency requiring fully autonomous security decisions',
      'Zero-trust in environments where trust infrastructure cannot be assumed',
    ],
    topRepos: [
      { name: 'openISRU', org: 'NASA', stars: 'Research', tech: 'In-situ resource utilization models' },
    ],
    topPapers: [
      { title: 'DARPA 10-Year Lunar Architecture Capability Study', venue: 'DARPA', year: 2024 },
    ],
    a11oyIntegration: 'a11oy governance operates in "lunar mode" for disconnected deployments — fully autonomous security decisions with cryptographic attestation that synchronizes when connectivity resumes. The proof chain maintains integrity across any latency or disconnection.',
    trl: 3,
  },
];

export const CYBER_AI_REPOS = [
  { name: 'adversarial-robustness-toolbox', org: 'Trusted-AI (IBM)', stars: '4.7K+', desc: 'Adversarial ML defense: evasion, poisoning, extraction, inference attacks', license: 'MIT' },
  { name: 'CrowdSec', org: 'crowdsecurity', stars: '8K+', desc: 'Behavior-based IPS with crowdsourced threat intelligence', license: 'MIT' },
  { name: 'suricata', org: 'OISF', stars: '4K+', desc: 'High-performance network threat detection engine', license: 'GPLv2' },
  { name: 'zeek', org: 'zeek', stars: '6K+', desc: 'Network analysis framework for security monitoring', license: 'BSD' },
  { name: 'MISP', org: 'MISP', stars: '5K+', desc: 'Threat intelligence sharing platform', license: 'AGPL' },
  { name: 'sigma', org: 'SigmaHQ', stars: '8K+', desc: 'Generic signature format for SIEM systems', license: 'LGPL' },
  { name: 'atomic-red-team', org: 'redcanaryco', stars: '9K+', desc: 'Adversary emulation mapped to MITRE ATT&CK', license: 'MIT' },
  { name: 'caldera', org: 'mitre', stars: '5K+', desc: 'Automated adversary emulation platform', license: 'Apache-2.0' },
  { name: 'noble-post-quantum', org: 'paulmillr', stars: '60K+ npm/wk', desc: 'TypeScript ML-KEM, ML-DSA, SLH-DSA post-quantum crypto', license: 'MIT' },
  { name: 'liboqs', org: 'open-quantum-safe', stars: '1.8K+', desc: 'C library for NIST PQC algorithms', license: 'MIT' },
  { name: 'OpenROAD', org: 'The-OpenROAD-Project', stars: '1.5K+', desc: 'Open-source chip design for hardware security', license: 'BSD' },
  { name: 'cheribsd', org: 'CTSRD-CHERI', stars: '300+', desc: 'CHERI capability-enhanced BSD for hardware-enforced memory safety', license: 'BSD' },
];
