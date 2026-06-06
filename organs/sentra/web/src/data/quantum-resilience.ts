export type PqcAlgorithm = 'CRYSTALS-Kyber' | 'CRYSTALS-Dilithium' | 'SPHINCS+' | 'FALCON' | 'Classic McEliece' | 'BIKE' | 'HQC';
export type MigrationStatus = 'migrated' | 'in_progress' | 'planned' | 'not_started' | 'blocked';
export type CryptoVulnerability = 'RSA-2048' | 'RSA-4096' | 'ECDSA-P256' | 'ECDH-P384' | 'DH-2048' | 'AES-128' | '3DES';

export interface QuantumCryptoInventory {
  id: string;
  system: string;
  environment: 'production' | 'staging' | 'corp' | 'ot';
  currentAlgorithm: CryptoVulnerability;
  targetAlgorithm: PqcAlgorithm;
  migrationStatus: MigrationStatus;
  quantumRiskLevel: 'critical' | 'high' | 'medium' | 'low';
  estimatedQbitThreshold: number;
  certificateExpiry: string;
  owner: string;
  dataClassification: 'top_secret' | 'secret' | 'confidential' | 'internal' | 'public';
  harvestNowDecryptLaterRisk: boolean;
  lastAuditedAt: string;
}

export type FoundryTrust = 'trusted' | 'conditionally_trusted' | 'untrusted' | 'sanctioned';
export type ProvenanceStatus = 'verified' | 'partial' | 'unverified' | 'counterfeit_risk';

export interface HardwareProvenanceChain {
  id: string;
  chipFamily: string;
  partNumber: string;
  foundry: string;
  foundryLocation: string;
  foundryTrust: FoundryTrust;
  fabricationNode: string;
  lotNumber: string;
  provenanceStatus: ProvenanceStatus;
  supplyChainHops: number;
  lastVerifiedAt: string;
  tamperEvidence: boolean;
  deployedIn: string;
  criticality: 'critical' | 'high' | 'medium' | 'low';
  complianceFlags: string[];
}

export type AttestationResult = 'pass' | 'fail' | 'degraded' | 'unavailable';
export type SideChannelType = 'power' | 'electromagnetic' | 'timing' | 'acoustic' | 'thermal' | 'cache';

export interface MicrosystemIntegrityRecord {
  id: string;
  device: string;
  deviceType: 'plc' | 'rtu' | 'sensor' | 'gateway' | 'hmi' | 'edge_compute' | 'fpga';
  firmwareVersion: string;
  firmwareHash: string;
  attestationResult: AttestationResult;
  rootOfTrustType: 'tpm_2.0' | 'secure_enclave' | 'puf' | 'dice' | 'none';
  lastAttestationAt: string;
  sideChannelAlerts: Array<{
    type: SideChannelType;
    detectedAt: string;
    confidence: number;
    description: string;
  }>;
  anomalyScore: number;
  zone: string;
  patchLevel: 'current' | 'behind' | 'critical_missing';
}

export type SensorHealth = 'optimal' | 'degraded' | 'calibration_needed' | 'offline' | 'compromised';

export interface PhotonicSensorNode {
  id: string;
  name: string;
  type: 'qkd_transmitter' | 'qkd_receiver' | 'photonic_switch' | 'fiber_tap_detector' | 'quantum_repeater' | 'photonic_interconnect';
  location: string;
  wavelength: string;
  health: SensorHealth;
  signalToNoiseRatio: number;
  quantumBitErrorRate: number;
  eavesdroppingDetected: boolean;
  lastCalibrationAt: string;
  driftPercentage: number;
  linkedChannelId: string;
  throughputGbps: number;
}

export type BioSubstrateType = 'dna_storage' | 'protein_compute' | 'biosensor_array' | 'organic_circuit' | 'neural_interface' | 'molecular_switch';
export type BioIntegrity = 'nominal' | 'degraded' | 'contaminated' | 'expired' | 'compromised';

export interface BioSubstrateAsset {
  id: string;
  name: string;
  type: BioSubstrateType;
  substrate: string;
  integrity: BioIntegrity;
  temperatureCelsius: number;
  temperatureRange: [number, number];
  contaminationRisk: number;
  dataExfiltrationVector: string | null;
  encryptionMethod: string;
  lastBioAssayAt: string;
  operationalHours: number;
  maxLifespanHours: number;
  location: string;
}

export type ThreatMaturity = 'theoretical' | 'lab_demonstrated' | 'weaponizable' | 'actively_exploited';

export interface ThreatHorizonVector {
  id: string;
  category: 'quantum_decryption' | 'photonic_side_channel' | 'bio_exploit' | 'microsystem_supply_chain' | 'cryogenic_attack' | 'ai_hardware_poisoning';
  title: string;
  description: string;
  maturity: ThreatMaturity;
  yearsToWeaponization: number | null;
  darpaProgram: string | null;
  mitigationAvailable: boolean;
  impactSeverity: 'catastrophic' | 'critical' | 'high' | 'medium' | 'low';
  affectedSectors: string[];
  lastUpdatedAt: string;
  sources: string[];
}

const now = new Date();
const daysAgo = (n: number) => new Date(now.getTime() - n * 86_400_000).toISOString();
const hoursAgo = (n: number) => new Date(now.getTime() - n * 3_600_000).toISOString();
const daysFromNow = (n: number) => new Date(now.getTime() + n * 86_400_000).toISOString();

export const quantumCryptoInventory: QuantumCryptoInventory[] = [
  {
    id: 'qci-001',
    system: 'Core Banking TLS Gateway',
    environment: 'production',
    currentAlgorithm: 'RSA-2048',
    targetAlgorithm: 'CRYSTALS-Kyber',
    migrationStatus: 'in_progress',
    quantumRiskLevel: 'critical',
    estimatedQbitThreshold: 4099,
    certificateExpiry: daysFromNow(89),
    owner: 'Platform Engineering',
    dataClassification: 'secret',
    harvestNowDecryptLaterRisk: true,
    lastAuditedAt: daysAgo(14),
  },
  {
    id: 'qci-002',
    system: 'Internal PKI Root CA',
    environment: 'corp',
    currentAlgorithm: 'ECDSA-P256',
    targetAlgorithm: 'CRYSTALS-Dilithium',
    migrationStatus: 'planned',
    quantumRiskLevel: 'critical',
    estimatedQbitThreshold: 2330,
    certificateExpiry: daysFromNow(412),
    owner: 'IT Security',
    dataClassification: 'top_secret',
    harvestNowDecryptLaterRisk: true,
    lastAuditedAt: daysAgo(7),
  },
  {
    id: 'qci-003',
    system: 'SCADA Control Plane VPN',
    environment: 'ot',
    currentAlgorithm: 'DH-2048',
    targetAlgorithm: 'CRYSTALS-Kyber',
    migrationStatus: 'not_started',
    quantumRiskLevel: 'critical',
    estimatedQbitThreshold: 4099,
    certificateExpiry: daysFromNow(210),
    owner: 'OT Security',
    dataClassification: 'secret',
    harvestNowDecryptLaterRisk: true,
    lastAuditedAt: daysAgo(45),
  },
  {
    id: 'qci-004',
    system: 'Customer API mTLS',
    environment: 'production',
    currentAlgorithm: 'ECDH-P384',
    targetAlgorithm: 'CRYSTALS-Kyber',
    migrationStatus: 'migrated',
    quantumRiskLevel: 'low',
    estimatedQbitThreshold: 2330,
    certificateExpiry: daysFromNow(180),
    owner: 'Platform Engineering',
    dataClassification: 'confidential',
    harvestNowDecryptLaterRisk: false,
    lastAuditedAt: daysAgo(3),
  },
  {
    id: 'qci-005',
    system: 'Data Warehouse Encryption at Rest',
    environment: 'production',
    currentAlgorithm: 'AES-128',
    targetAlgorithm: 'Classic McEliece',
    migrationStatus: 'blocked',
    quantumRiskLevel: 'high',
    estimatedQbitThreshold: 6681,
    certificateExpiry: daysFromNow(365),
    owner: 'Data Engineering',
    dataClassification: 'secret',
    harvestNowDecryptLaterRisk: true,
    lastAuditedAt: daysAgo(21),
  },
  {
    id: 'qci-006',
    system: 'Employee SSO (OIDC)',
    environment: 'corp',
    currentAlgorithm: 'RSA-4096',
    targetAlgorithm: 'FALCON',
    migrationStatus: 'in_progress',
    quantumRiskLevel: 'medium',
    estimatedQbitThreshold: 8194,
    certificateExpiry: daysFromNow(60),
    owner: 'IT Security',
    dataClassification: 'internal',
    harvestNowDecryptLaterRisk: false,
    lastAuditedAt: daysAgo(10),
  },
  {
    id: 'qci-007',
    system: 'IoT Sensor Mesh Auth',
    environment: 'ot',
    currentAlgorithm: 'ECDSA-P256',
    targetAlgorithm: 'SPHINCS+',
    migrationStatus: 'not_started',
    quantumRiskLevel: 'high',
    estimatedQbitThreshold: 2330,
    certificateExpiry: daysFromNow(140),
    owner: 'OT Security',
    dataClassification: 'confidential',
    harvestNowDecryptLaterRisk: true,
    lastAuditedAt: daysAgo(30),
  },
  {
    id: 'qci-008',
    system: 'Backup Encryption Keys',
    environment: 'production',
    currentAlgorithm: 'RSA-2048',
    targetAlgorithm: 'CRYSTALS-Kyber',
    migrationStatus: 'planned',
    quantumRiskLevel: 'high',
    estimatedQbitThreshold: 4099,
    certificateExpiry: daysFromNow(270),
    owner: 'Infrastructure',
    dataClassification: 'secret',
    harvestNowDecryptLaterRisk: true,
    lastAuditedAt: daysAgo(18),
  },
];

export const hardwareProvenanceChains: HardwareProvenanceChain[] = [
  {
    id: 'hpc-001',
    chipFamily: 'Cortex-M33 Secure',
    partNumber: 'STM32U585AI',
    foundry: 'TSMC',
    foundryLocation: 'Hsinchu, Taiwan',
    foundryTrust: 'trusted',
    fabricationNode: '40nm',
    lotNumber: 'TSMC-2026-Q1-4471',
    provenanceStatus: 'verified',
    supplyChainHops: 3,
    lastVerifiedAt: daysAgo(5),
    tamperEvidence: false,
    deployedIn: 'PLC Controller Array — Zone 4',
    criticality: 'critical',
    complianceFlags: ['DFARS 252.204-7012', 'NIST SP 800-193'],
  },
  {
    id: 'hpc-002',
    chipFamily: 'Xilinx Artix UltraScale+',
    partNumber: 'XCAU25P-2FFVB676I',
    foundry: 'TSMC',
    foundryLocation: 'Tainan, Taiwan',
    foundryTrust: 'trusted',
    fabricationNode: '16nm FinFET',
    lotNumber: 'TSMC-2025-Q4-8812',
    provenanceStatus: 'verified',
    supplyChainHops: 4,
    lastVerifiedAt: daysAgo(12),
    tamperEvidence: false,
    deployedIn: 'FPGA Acceleration Cluster — Data Center',
    criticality: 'high',
    complianceFlags: ['NIST SP 800-193', 'IEC 62443'],
  },
  {
    id: 'hpc-003',
    chipFamily: 'Intel Xeon Scalable',
    partNumber: '8490H',
    foundry: 'Intel Foundry Services',
    foundryLocation: 'Chandler, Arizona, USA',
    foundryTrust: 'trusted',
    fabricationNode: 'Intel 4',
    lotNumber: 'IFS-2026-Q1-0093',
    provenanceStatus: 'verified',
    supplyChainHops: 2,
    lastVerifiedAt: daysAgo(3),
    tamperEvidence: false,
    deployedIn: 'SOC Compute Infrastructure',
    criticality: 'critical',
    complianceFlags: ['FIPS 140-3', 'DFARS 252.204-7012'],
  },
  {
    id: 'hpc-004',
    chipFamily: 'NXP i.MX RT1170',
    partNumber: 'MIMXRT1176DVMAA',
    foundry: 'GlobalFoundries',
    foundryLocation: 'Dresden, Germany',
    foundryTrust: 'conditionally_trusted',
    fabricationNode: '28nm',
    lotNumber: 'GF-2025-Q3-5520',
    provenanceStatus: 'partial',
    supplyChainHops: 6,
    lastVerifiedAt: daysAgo(28),
    tamperEvidence: false,
    deployedIn: 'HMI Workstation Controllers',
    criticality: 'high',
    complianceFlags: ['IEC 62443'],
  },
  {
    id: 'hpc-005',
    chipFamily: 'Microchip ATECC608B',
    partNumber: 'ATECC608B-TFLXTLS',
    foundry: 'Unknown Subcontractor',
    foundryLocation: 'Shenzhen, China',
    foundryTrust: 'untrusted',
    fabricationNode: '130nm',
    lotNumber: 'UNK-2025-Q2-BATCH-7',
    provenanceStatus: 'counterfeit_risk',
    supplyChainHops: 9,
    lastVerifiedAt: daysAgo(60),
    tamperEvidence: true,
    deployedIn: 'IoT Sensor Authentication Module',
    criticality: 'critical',
    complianceFlags: ['DFARS NON-COMPLIANT'],
  },
  {
    id: 'hpc-006',
    chipFamily: 'Infineon OPTIGA TPM 2.0',
    partNumber: 'SLB9672',
    foundry: 'TSMC',
    foundryLocation: 'Hsinchu, Taiwan',
    foundryTrust: 'trusted',
    fabricationNode: '65nm',
    lotNumber: 'TSMC-2025-Q4-1190',
    provenanceStatus: 'verified',
    supplyChainHops: 3,
    lastVerifiedAt: daysAgo(8),
    tamperEvidence: false,
    deployedIn: 'Server Fleet TPM Modules',
    criticality: 'critical',
    complianceFlags: ['FIPS 140-3', 'Common Criteria EAL4+'],
  },
];

export const microsystemIntegrityRecords: MicrosystemIntegrityRecord[] = [
  {
    id: 'mir-001',
    device: 'PLC-Reactor-1',
    deviceType: 'plc',
    firmwareVersion: '4.2.1-sec',
    firmwareHash: 'sha256:a3f8c1d...7e2b',
    attestationResult: 'pass',
    rootOfTrustType: 'tpm_2.0',
    lastAttestationAt: hoursAgo(2),
    sideChannelAlerts: [],
    anomalyScore: 12,
    zone: 'Zone 4 — Reactor Control',
    patchLevel: 'current',
  },
  {
    id: 'mir-002',
    device: 'RTU-Substation-7',
    deviceType: 'rtu',
    firmwareVersion: '3.8.0',
    firmwareHash: 'sha256:e7d2b4f...1c9a',
    attestationResult: 'fail',
    rootOfTrustType: 'none',
    lastAttestationAt: hoursAgo(6),
    sideChannelAlerts: [
      {
        type: 'electromagnetic',
        detectedAt: hoursAgo(4),
        confidence: 78,
        description: 'Anomalous EM emissions detected during key exchange — possible side-channel probe',
      },
    ],
    anomalyScore: 84,
    zone: 'Zone 6 — Substation Grid',
    patchLevel: 'critical_missing',
  },
  {
    id: 'mir-003',
    device: 'GW-Edge-Compute-02',
    deviceType: 'edge_compute',
    firmwareVersion: '2.1.4-hardened',
    firmwareHash: 'sha256:b4c9e1a...3d5f',
    attestationResult: 'pass',
    rootOfTrustType: 'secure_enclave',
    lastAttestationAt: hoursAgo(1),
    sideChannelAlerts: [],
    anomalyScore: 8,
    zone: 'Zone 3 — Edge Processing',
    patchLevel: 'current',
  },
  {
    id: 'mir-004',
    device: 'HMI-Panel-A3',
    deviceType: 'hmi',
    firmwareVersion: '5.0.2',
    firmwareHash: 'sha256:f1a2b3c...8d4e',
    attestationResult: 'degraded',
    rootOfTrustType: 'dice',
    lastAttestationAt: hoursAgo(12),
    sideChannelAlerts: [
      {
        type: 'timing',
        detectedAt: hoursAgo(8),
        confidence: 62,
        description: 'Timing variance in authentication handshake — potential oracle attack vector',
      },
    ],
    anomalyScore: 56,
    zone: 'Zone 2 — Operator Floor',
    patchLevel: 'behind',
  },
  {
    id: 'mir-005',
    device: 'FPGA-Accel-Node-1',
    deviceType: 'fpga',
    firmwareVersion: '1.0.3-bitstream',
    firmwareHash: 'sha256:9c8d7e6...2f1a',
    attestationResult: 'pass',
    rootOfTrustType: 'puf',
    lastAttestationAt: hoursAgo(3),
    sideChannelAlerts: [],
    anomalyScore: 5,
    zone: 'Zone 1 — Data Center',
    patchLevel: 'current',
  },
  {
    id: 'mir-006',
    device: 'Sensor-Array-Temp-12',
    deviceType: 'sensor',
    firmwareVersion: '1.4.0',
    firmwareHash: 'sha256:d5e6f7a...0b1c',
    attestationResult: 'unavailable',
    rootOfTrustType: 'none',
    lastAttestationAt: daysAgo(30),
    sideChannelAlerts: [
      {
        type: 'power',
        detectedAt: daysAgo(2),
        confidence: 45,
        description: 'Unusual power draw pattern during idle state — monitoring for DPA signature',
      },
    ],
    anomalyScore: 41,
    zone: 'Zone 5 — Environmental',
    patchLevel: 'behind',
  },
  {
    id: 'mir-007',
    device: 'PLC-Boiler-2',
    deviceType: 'plc',
    firmwareVersion: '4.1.0',
    firmwareHash: 'sha256:c2d3e4f...5a6b',
    attestationResult: 'fail',
    rootOfTrustType: 'tpm_2.0',
    lastAttestationAt: hoursAgo(1),
    sideChannelAlerts: [
      {
        type: 'cache',
        detectedAt: hoursAgo(0.5),
        confidence: 91,
        description: 'Cache timing attack signature detected — Flush+Reload pattern on crypto routines',
      },
    ],
    anomalyScore: 92,
    zone: 'Zone 4 — Boiler Control',
    patchLevel: 'critical_missing',
  },
];

export const photonicSensorNodes: PhotonicSensorNode[] = [
  {
    id: 'psn-001',
    name: 'QKD-TX-Primary',
    type: 'qkd_transmitter',
    location: 'DC-East — Quantum Lab',
    wavelength: '1550nm C-Band',
    health: 'optimal',
    signalToNoiseRatio: 34.2,
    quantumBitErrorRate: 0.8,
    eavesdroppingDetected: false,
    lastCalibrationAt: daysAgo(3),
    driftPercentage: 0.3,
    linkedChannelId: 'qkd-ch-alpha',
    throughputGbps: 1.2,
  },
  {
    id: 'psn-002',
    name: 'QKD-RX-Primary',
    type: 'qkd_receiver',
    location: 'DC-West — Quantum Lab',
    wavelength: '1550nm C-Band',
    health: 'optimal',
    signalToNoiseRatio: 31.8,
    quantumBitErrorRate: 1.1,
    eavesdroppingDetected: false,
    lastCalibrationAt: daysAgo(3),
    driftPercentage: 0.5,
    linkedChannelId: 'qkd-ch-alpha',
    throughputGbps: 1.2,
  },
  {
    id: 'psn-003',
    name: 'Photonic-SW-Core-1',
    type: 'photonic_switch',
    location: 'DC-East — Rack 14',
    wavelength: '1310nm O-Band',
    health: 'degraded',
    signalToNoiseRatio: 22.1,
    quantumBitErrorRate: 3.4,
    eavesdroppingDetected: false,
    lastCalibrationAt: daysAgo(18),
    driftPercentage: 4.7,
    linkedChannelId: 'ph-backbone-01',
    throughputGbps: 25.6,
  },
  {
    id: 'psn-004',
    name: 'Fiber-Tap-Det-Perimeter',
    type: 'fiber_tap_detector',
    location: 'Building Perimeter — MDF',
    wavelength: '1550nm C-Band',
    health: 'compromised',
    signalToNoiseRatio: 8.4,
    quantumBitErrorRate: 12.7,
    eavesdroppingDetected: true,
    lastCalibrationAt: daysAgo(1),
    driftPercentage: 18.3,
    linkedChannelId: 'fiber-perim-01',
    throughputGbps: 0.0,
  },
  {
    id: 'psn-005',
    name: 'Q-Repeater-Mid-01',
    type: 'quantum_repeater',
    location: 'Relay Station — 42km Mark',
    wavelength: '1550nm C-Band',
    health: 'calibration_needed',
    signalToNoiseRatio: 18.9,
    quantumBitErrorRate: 5.2,
    eavesdroppingDetected: false,
    lastCalibrationAt: daysAgo(45),
    driftPercentage: 8.1,
    linkedChannelId: 'qkd-ch-alpha',
    throughputGbps: 0.8,
  },
  {
    id: 'psn-006',
    name: 'PIC-Interconnect-Rack7',
    type: 'photonic_interconnect',
    location: 'DC-East — Rack 7',
    wavelength: '850nm VCSEL',
    health: 'optimal',
    signalToNoiseRatio: 28.5,
    quantumBitErrorRate: 0.4,
    eavesdroppingDetected: false,
    lastCalibrationAt: daysAgo(7),
    driftPercentage: 0.9,
    linkedChannelId: 'pic-rack-cluster',
    throughputGbps: 51.2,
  },
];

export const bioSubstrateAssets: BioSubstrateAsset[] = [
  {
    id: 'bsa-001',
    name: 'DNA-Store-Archive-Alpha',
    type: 'dna_storage',
    substrate: 'Synthetic oligonucleotide array',
    integrity: 'nominal',
    temperatureCelsius: -20,
    temperatureRange: [-25, -15],
    contaminationRisk: 3,
    dataExfiltrationVector: null,
    encryptionMethod: 'AES-256-GCM + PQC envelope',
    lastBioAssayAt: daysAgo(14),
    operationalHours: 8760,
    maxLifespanHours: 87600,
    location: 'Bio-Secure Vault — Sub-Level 2',
  },
  {
    id: 'bsa-002',
    name: 'Protein-Compute-Node-1',
    type: 'protein_compute',
    substrate: 'Engineered enzyme cascade (lysate)',
    integrity: 'degraded',
    temperatureCelsius: 37.2,
    temperatureRange: [35, 39],
    contaminationRisk: 28,
    dataExfiltrationVector: 'Metabolic byproduct analysis could reveal computation patterns',
    encryptionMethod: 'Molecular obfuscation layer v2',
    lastBioAssayAt: daysAgo(3),
    operationalHours: 2160,
    maxLifespanHours: 4320,
    location: 'Bio-Compute Lab — Room 4C',
  },
  {
    id: 'bsa-003',
    name: 'BioSensor-Grid-Perimeter',
    type: 'biosensor_array',
    substrate: 'Aptamer-functionalized graphene FET',
    integrity: 'nominal',
    temperatureCelsius: 22.1,
    temperatureRange: [18, 28],
    contaminationRisk: 5,
    dataExfiltrationVector: null,
    encryptionMethod: 'TLS 1.3 + CRYSTALS-Kyber hybrid',
    lastBioAssayAt: daysAgo(7),
    operationalHours: 4380,
    maxLifespanHours: 26280,
    location: 'Facility Perimeter — Bio-Chem Detection Ring',
  },
  {
    id: 'bsa-004',
    name: 'Organic-Circuit-Prototype-2',
    type: 'organic_circuit',
    substrate: 'Conjugated polymer (P3HT/PCBM)',
    integrity: 'compromised',
    temperatureCelsius: 24.8,
    temperatureRange: [20, 30],
    contaminationRisk: 67,
    dataExfiltrationVector: 'UV fluorescence signature leaks gate state information',
    encryptionMethod: 'None — research prototype',
    lastBioAssayAt: hoursAgo(12),
    operationalHours: 720,
    maxLifespanHours: 2160,
    location: 'R&D Lab — Organic Electronics Wing',
  },
  {
    id: 'bsa-005',
    name: 'Neural-Interface-Eval-Unit',
    type: 'neural_interface',
    substrate: 'MEA (multi-electrode array) on flexible substrate',
    integrity: 'nominal',
    temperatureCelsius: 36.8,
    temperatureRange: [36, 38],
    contaminationRisk: 8,
    dataExfiltrationVector: null,
    encryptionMethod: 'End-to-end neural signal encryption (NSE-1)',
    lastBioAssayAt: daysAgo(2),
    operationalHours: 1440,
    maxLifespanHours: 8760,
    location: 'Neurotech Eval Lab — Faraday Room',
  },
  {
    id: 'bsa-006',
    name: 'MolSwitch-Logic-Gate-Array',
    type: 'molecular_switch',
    substrate: 'Rotaxane-based molecular machines',
    integrity: 'degraded',
    temperatureCelsius: 4.1,
    temperatureRange: [2, 8],
    contaminationRisk: 15,
    dataExfiltrationVector: 'Spectroscopic readout of switch states possible at close range',
    encryptionMethod: 'Physical isolation + Faraday cage',
    lastBioAssayAt: daysAgo(5),
    operationalHours: 3600,
    maxLifespanHours: 17520,
    location: 'Molecular Computing Lab — Clean Room B',
  },
];

export const threatHorizonVectors: ThreatHorizonVector[] = [
  {
    id: 'thv-001',
    category: 'quantum_decryption',
    title: 'Cryptographically Relevant Quantum Computer (CRQC)',
    description: 'A fault-tolerant quantum computer capable of running Shor\'s algorithm to break RSA-2048 and ECDSA-P256 in polynomial time. NIST estimates 4,099 logical qubits required for RSA-2048.',
    maturity: 'lab_demonstrated',
    yearsToWeaponization: 7,
    darpaProgram: 'DARPA US2QC (Underexplored Systems for Utility-Scale Quantum Computing)',
    mitigationAvailable: true,
    impactSeverity: 'catastrophic',
    affectedSectors: ['Financial Services', 'Government', 'Defense', 'Healthcare', 'Critical Infrastructure'],
    lastUpdatedAt: daysAgo(2),
    sources: ['NIST IR 8413', 'NSA CNSA 2.0', 'DARPA US2QC Program'],
  },
  {
    id: 'thv-002',
    category: 'photonic_side_channel',
    title: 'Photonic Interconnect Eavesdropping via Fiber Bend Coupling',
    description: 'Exploitation of evanescent field leakage in bent optical fibers to intercept data without disrupting signal integrity. Lab demonstrations show successful interception at macro-bend radii below 15mm.',
    maturity: 'lab_demonstrated',
    yearsToWeaponization: 3,
    darpaProgram: 'DARPA LUMOS (Lasers for Universal Microscale Optical Systems)',
    mitigationAvailable: true,
    impactSeverity: 'high',
    affectedSectors: ['Telecommunications', 'Data Centers', 'Defense', 'Financial Services'],
    lastUpdatedAt: daysAgo(8),
    sources: ['IEEE Photonics Journal 2025', 'DARPA LUMOS Reports'],
  },
  {
    id: 'thv-003',
    category: 'bio_exploit',
    title: 'DNA Storage Payload Injection via Synthesis Contamination',
    description: 'Adversarial nucleotide sequences embedded during DNA synthesis that encode executable payloads, exploiting the DNA-to-digital readback pipeline. Demonstrated in controlled settings with modified gene synthesis orders.',
    maturity: 'lab_demonstrated',
    yearsToWeaponization: 5,
    darpaProgram: 'DARPA Safe Genes',
    mitigationAvailable: false,
    impactSeverity: 'critical',
    affectedSectors: ['Biotech', 'Defense', 'Healthcare', 'Data Storage'],
    lastUpdatedAt: daysAgo(15),
    sources: ['USENIX Security 2025', 'DARPA Safe Genes'],
  },
  {
    id: 'thv-004',
    category: 'microsystem_supply_chain',
    title: 'Hardware Trojan Insertion at Untrusted Foundry',
    description: 'Insertion of malicious logic gates during semiconductor fabrication at foundries outside trusted oversight. Trojan circuitry can exfiltrate keys, disable safety interlocks, or create covert channels activated by rare trigger conditions.',
    maturity: 'weaponizable',
    yearsToWeaponization: null,
    darpaProgram: 'DARPA SHIELD (Supply Chain Hardware Integrity for Electronics Defense)',
    mitigationAvailable: true,
    impactSeverity: 'catastrophic',
    affectedSectors: ['Defense', 'Critical Infrastructure', 'Automotive', 'Aerospace'],
    lastUpdatedAt: daysAgo(5),
    sources: ['DARPA SHIELD Final Report', 'NIST SP 800-161r1'],
  },
  {
    id: 'thv-005',
    category: 'cryogenic_attack',
    title: 'Cold Boot Attack on Cryogenic Quantum Control Electronics',
    description: 'Physical attack exploiting data remanence in SRAM/DRAM of cryogenic control systems operating at 4K. Calibration data and quantum error correction keys persist in memory after warm-up cycles, enabling extraction of quantum circuit configurations.',
    maturity: 'theoretical',
    yearsToWeaponization: 10,
    darpaProgram: 'DARPA ONISQ (Optimization with Noisy Intermediate-Scale Quantum devices)',
    mitigationAvailable: false,
    impactSeverity: 'high',
    affectedSectors: ['Quantum Computing', 'Defense', 'Research'],
    lastUpdatedAt: daysAgo(20),
    sources: ['CCC Quantum Security Workshop 2025', 'arXiv:2504.12881'],
  },
  {
    id: 'thv-006',
    category: 'ai_hardware_poisoning',
    title: 'Adversarial Weight Injection via Compromised AI Accelerator Firmware',
    description: 'Manipulation of neural network weights during inference by compromised firmware on AI accelerators (GPUs, TPUs, NPUs). Modified firmware subtly alters matrix multiply results to produce adversary-chosen misclassifications on specific inputs.',
    maturity: 'weaponizable',
    yearsToWeaponization: null,
    darpaProgram: 'DARPA GARD (Guaranteeing AI Robustness against Deception)',
    mitigationAvailable: true,
    impactSeverity: 'critical',
    affectedSectors: ['Defense', 'Autonomous Systems', 'Critical Infrastructure', 'Financial Services'],
    lastUpdatedAt: daysAgo(3),
    sources: ['DARPA GARD Phase 3', 'NDSS 2026'],
  },
  {
    id: 'thv-007',
    category: 'quantum_decryption',
    title: 'Harvest Now, Decrypt Later (HNDL) Campaigns',
    description: 'State-sponsored actors intercepting and storing encrypted traffic today for future decryption when quantum computers become available. NSA has confirmed active HNDL operations by multiple nation-states targeting diplomatic, defense, and financial communications.',
    maturity: 'actively_exploited',
    yearsToWeaponization: null,
    darpaProgram: null,
    mitigationAvailable: true,
    impactSeverity: 'critical',
    affectedSectors: ['Government', 'Defense', 'Financial Services', 'Telecommunications', 'Healthcare'],
    lastUpdatedAt: daysAgo(1),
    sources: ['NSA Cybersecurity Advisory 2025', 'CISA Quantum Readiness'],
  },
  {
    id: 'thv-008',
    category: 'photonic_side_channel',
    title: 'Quantum Key Distribution Channel Blinding Attack',
    description: 'Detector blinding attack on QKD single-photon detectors using bright illumination to force detectors into linear mode, allowing an eavesdropper to control detection outcomes and extract the raw key without increasing the quantum bit error rate.',
    maturity: 'weaponizable',
    yearsToWeaponization: null,
    darpaProgram: 'DARPA QUIST (Quantum Information Science and Technology)',
    mitigationAvailable: true,
    impactSeverity: 'critical',
    affectedSectors: ['Telecommunications', 'Government', 'Defense', 'Financial Services'],
    lastUpdatedAt: daysAgo(10),
    sources: ['Nature Photonics 2024', 'ETSI QKD Security Proofs'],
  },
];
