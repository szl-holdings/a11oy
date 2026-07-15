// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — artifacts/sentra/src/data/seed-data.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
export {
  type MspAlert as Alert,
  type MspClient as Client,
  type MspContract as Contract,
  type MspDevice as Device,
  type MspTechnician as Technician,
  type MspTicket as Ticket,
  mspAlerts as alerts,
  mspClients as clients,
  mspContracts as contracts,
  mspDevices as devices,
  mspIncidentTimeline as incidentTimeline,
  mspRevenueData as revenueData,
  mspTechnicians as technicians,
  mspTickets as tickets,
  mspUptimeData as uptimeData,
} from '@szl-holdings/services';

export type ProjectStatus = 'research' | 'development' | 'testing' | 'deployed';

export interface Project {
  id: string;
  name: string;
  status: ProjectStatus;
  domain: string;
  description: string;
  accuracy: number;
  loss: number;
  inferenceTime: number;
  progress: number;
  team: { avatar: string }[];
  updatedAt: string;
  startDate: string;
}

export interface Experiment {
  id: string;
  projectId: string;
  name: string;
  status: 'running' | 'completed' | 'failed' | 'queued';
  hypothesis: string;
  results: string;
  duration: string;
  startDate: string;
  metrics: { epoch: number; loss: number; accuracy: number; valAccuracy?: number }[];
  hyperparameters: Record<string, string | number>;
}

export interface Model {
  id: string;
  name: string;
  projectId: string;
  status: 'production' | 'staging' | 'training' | 'archived';
  architecture: string;
  version: string;
  parameters: string;
  accuracy: number;
  speed: number;
  cost: number;
  performanceHistory: { date: string; accuracy: number; latency: number }[];
}

export type InsightCategory = 'success' | 'warning' | 'trend' | 'discovery';

export interface Insight {
  id: string;
  title: string;
  description: string;
  category: InsightCategory;
  impact: 'high' | 'medium' | 'low';
  confidence: number;
  sourceExperiment: string;
  date: string;
}

export const projects: Project[] = [
  {
    id: 'proj-001',
    name: 'Threat Vector Classifier',
    status: 'deployed',
    domain: 'Cybersecurity',
    description:
      'Multi-class neural network for real-time threat vector classification across network traffic patterns.',
    accuracy: 97.4,
    loss: 0.041,
    inferenceTime: 12,
    progress: 100,
    team: [{ avatar: 'AC' }, { avatar: 'RP' }, { avatar: 'SK' }, { avatar: 'JT' }],
    updatedAt: '2026-04-14',
    startDate: '2025-08-01',
  },
  {
    id: 'proj-002',
    name: 'Geopolitical Risk Forecaster',
    status: 'testing',
    domain: 'Intelligence',
    description:
      'LSTM-based forecasting model combining OSINT signals with structured geopolitical indicators.',
    accuracy: 84.1,
    loss: 0.183,
    inferenceTime: 45,
    progress: 82,
    team: [{ avatar: 'MO' }, { avatar: 'LF' }, { avatar: 'DW' }],
    updatedAt: '2026-04-12',
    startDate: '2025-10-15',
  },
  {
    id: 'proj-003',
    name: 'Entity Resolution Engine',
    status: 'development',
    domain: 'Data Fusion',
    description:
      'Graph-based entity resolution across disparate intelligence sources using transformer embeddings.',
    accuracy: 91.6,
    loss: 0.098,
    inferenceTime: 28,
    progress: 64,
    team: [{ avatar: 'BN' }, { avatar: 'EV' }, { avatar: 'TA' }],
    updatedAt: '2026-04-10',
    startDate: '2025-12-01',
  },
  {
    id: 'proj-004',
    name: 'Anomaly Detection Suite',
    status: 'research',
    domain: 'Monitoring',
    description:
      'Unsupervised anomaly detection across multi-variate time-series telemetry streams.',
    accuracy: 76.3,
    loss: 0.312,
    inferenceTime: 8,
    progress: 31,
    team: [{ avatar: 'CR' }, { avatar: 'NS' }],
    updatedAt: '2026-04-08',
    startDate: '2026-02-01',
  },
  {
    id: 'proj-005',
    name: 'NLP Signal Extractor',
    status: 'development',
    domain: 'Natural Language',
    description:
      'Fine-tuned LLM pipeline for extracting structured intelligence signals from unstructured text.',
    accuracy: 88.9,
    loss: 0.142,
    inferenceTime: 62,
    progress: 57,
    team: [{ avatar: 'YP' }, { avatar: 'AM' }, { avatar: 'RC' }, { avatar: 'FD' }],
    updatedAt: '2026-04-11',
    startDate: '2025-11-10',
  },
];

export const experiments: Experiment[] = [
  {
    id: 'exp-001',
    projectId: 'proj-001',
    name: 'ResNet-50 Fine-tune v3',
    status: 'completed',
    hypothesis: 'Increasing dropout to 0.4 will reduce overfitting on imbalanced threat classes.',
    results: 'Validation accuracy improved 1.8pp. F1 on rare classes improved from 0.71 to 0.84.',
    duration: '6h 22m',
    startDate: '2026-04-08',
    metrics: [
      { epoch: 1, loss: 0.81, accuracy: 72.1 },
      { epoch: 5, loss: 0.44, accuracy: 85.3 },
      { epoch: 10, loss: 0.21, accuracy: 93.7 },
      { epoch: 15, loss: 0.09, accuracy: 96.2 },
      { epoch: 20, loss: 0.04, accuracy: 97.4 },
    ],
    hyperparameters: { lr: 0.0003, dropout: 0.4, epochs: 20, batch_size: 128 },
  },
  {
    id: 'exp-002',
    projectId: 'proj-002',
    name: 'Bi-LSTM Attention v2',
    status: 'running',
    hypothesis:
      'Attention mechanism will improve long-range temporal dependencies in geopolitical sequences.',
    results: '',
    duration: '2h 14m',
    startDate: '2026-04-14',
    metrics: [
      { epoch: 1, loss: 0.62, accuracy: 68.4 },
      { epoch: 3, loss: 0.41, accuracy: 79.1 },
      { epoch: 5, loss: 0.29, accuracy: 83.6 },
    ],
    hyperparameters: { lr: 0.001, hidden_units: 256, seq_len: 60, attention_heads: 8 },
  },
  {
    id: 'exp-003',
    projectId: 'proj-003',
    name: 'Graph Attention Network',
    status: 'completed',
    hypothesis:
      'GAT layers will outperform GCN on heterogeneous entity graphs with varying edge weights.',
    results: 'GAT achieved 91.6% accuracy vs 87.2% for baseline GCN. 2.1x inference speedup.',
    duration: '11h 47m',
    startDate: '2026-04-03',
    metrics: [
      { epoch: 1, loss: 0.74, accuracy: 65.2 },
      { epoch: 8, loss: 0.31, accuracy: 84.9 },
      { epoch: 16, loss: 0.14, accuracy: 90.1 },
      { epoch: 24, loss: 0.09, accuracy: 91.6 },
    ],
    hyperparameters: { lr: 0.0005, layers: 4, heads: 8, edge_dropout: 0.2 },
  },
  {
    id: 'exp-004',
    projectId: 'proj-004',
    name: 'Autoencoder Threshold v1',
    status: 'failed',
    hypothesis:
      'Reconstruction error threshold tuned on rolling 7-day baseline will reduce false positives by 30%.',
    results: 'Experiment failed: OOM on batch normalization with 1024-dim latent space.',
    duration: '1h 03m',
    startDate: '2026-04-06',
    metrics: [{ epoch: 1, loss: 1.42, accuracy: 48.3 }],
    hyperparameters: { lr: 0.001, latent_dim: 1024, window: 7, threshold_sigma: 2.5 },
  },
  {
    id: 'exp-005',
    projectId: 'proj-005',
    name: 'Mistral-7B LoRA Finetune',
    status: 'queued',
    hypothesis:
      'LoRA adapters at r=64 will match full fine-tune quality at 12x lower compute cost.',
    results: '',
    duration: '—',
    startDate: '2026-04-16',
    metrics: [],
    hyperparameters: { lora_r: 64, lora_alpha: 128, epochs: 3, batch_size: 8 },
  },
];

export const models: Model[] = [
  {
    id: 'mdl-001',
    name: 'ThreatVec-v3',
    projectId: 'proj-001',
    status: 'production',
    architecture: 'ResNet-50',
    version: '3.2.1',
    parameters: '25.6M',
    accuracy: 97.4,
    speed: 92,
    cost: 38,
    performanceHistory: [
      { date: '2026-01', accuracy: 93.1, latency: 18 },
      { date: '2026-02', accuracy: 95.4, latency: 15 },
      { date: '2026-03', accuracy: 96.8, latency: 13 },
      { date: '2026-04', accuracy: 97.4, latency: 12 },
    ],
  },
  {
    id: 'mdl-002',
    name: 'GeoRisk-BiLSTM',
    projectId: 'proj-002',
    status: 'staging',
    architecture: 'Bi-LSTM',
    version: '2.0.0-rc',
    parameters: '8.2M',
    accuracy: 84.1,
    speed: 74,
    cost: 52,
    performanceHistory: [
      { date: '2026-02', accuracy: 79.3, latency: 52 },
      { date: '2026-03', accuracy: 82.7, latency: 48 },
      { date: '2026-04', accuracy: 84.1, latency: 45 },
    ],
  },
  {
    id: 'mdl-003',
    name: 'EntityGAT-v1',
    projectId: 'proj-003',
    status: 'staging',
    architecture: 'Graph Attention Network',
    version: '1.4.0',
    parameters: '14.1M',
    accuracy: 91.6,
    speed: 81,
    cost: 45,
    performanceHistory: [
      { date: '2026-03', accuracy: 87.2, latency: 35 },
      { date: '2026-04', accuracy: 91.6, latency: 28 },
    ],
  },
  {
    id: 'mdl-004',
    name: 'NLPSignal-Mistral',
    projectId: 'proj-005',
    status: 'training',
    architecture: 'Mistral-7B LoRA',
    version: '0.1.0-alpha',
    parameters: '7B',
    accuracy: 88.9,
    speed: 42,
    cost: 81,
    performanceHistory: [{ date: '2026-04', accuracy: 88.9, latency: 62 }],
  },
];

export const insights: Insight[] = [
  {
    id: 'ins-001',
    title: 'ThreatVec-v3 surpasses 97% accuracy threshold',
    description:
      'The latest production model hit 97.4% validation accuracy — a 4.3pp improvement from v2. Rare class F1 scores are now consistently above 0.84, enabling high-confidence automated triage.',
    category: 'success',
    impact: 'high',
    confidence: 96,
    sourceExperiment: 'ResNet-50 Fine-tune v3',
    date: '2026-04-14',
  },
  {
    id: 'ins-002',
    title: 'GeoRisk model underperforms on Pacific-region signals',
    description:
      'Recall for Pacific-region geopolitical events is 12pp below Atlantic baseline. Training data imbalance likely cause — Pacific events represent only 8% of training corpus.',
    category: 'warning',
    impact: 'medium',
    confidence: 84,
    sourceExperiment: 'Bi-LSTM Attention v2',
    date: '2026-04-12',
  },
  {
    id: 'ins-003',
    title: 'Graph attention outperforms GCN by 4.4pp on entity resolution',
    description:
      'Consistent across 3 cross-validation folds with p < 0.01. Heterogeneous edge type encoding is the likely differentiating factor.',
    category: 'discovery',
    impact: 'high',
    confidence: 91,
    sourceExperiment: 'Graph Attention Network',
    date: '2026-04-10',
  },
  {
    id: 'ins-004',
    title: 'NLP extraction latency trending toward SLA boundary',
    description:
      'P95 inference latency increased from 48ms to 62ms over the past 30 days as document length distributions shift. Quantization or batching optimization needed before production.',
    category: 'trend',
    impact: 'medium',
    confidence: 78,
    sourceExperiment: 'Mistral-7B LoRA Finetune',
    date: '2026-04-11',
  },
  {
    id: 'ins-005',
    title: 'Anomaly detector false positive rate stable after threshold recalibration',
    description:
      'Post-recalibration FPR dropped from 2.3% to 0.8%. 7-day rolling baseline approach is holding across seasonal shifts.',
    category: 'success',
    impact: 'low',
    confidence: 88,
    sourceExperiment: 'Autoencoder Threshold v1',
    date: '2026-04-08',
  },
];

export function getResearchHealthScore(): number {
  const deployedCount = projects.filter((p) => p.status === 'deployed').length;
  const completedExps = experiments.filter((e) => e.status === 'completed').length;
  const productionModels = models.filter((m) => m.status === 'production').length;
  const avgAccuracy = models.reduce((sum, m) => sum + m.accuracy, 0) / models.length;
  return Math.round(
    deployedCount * 15 + completedExps * 10 + productionModels * 20 + avgAccuracy * 0.4,
  );
}
