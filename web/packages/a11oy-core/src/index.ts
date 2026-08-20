export {
  type CredenceVector,
  normalize as normalizeCredenceVector,
  fisherRaoDistance,
  fisherDiagonal,
} from './geometry/fisher_manifold';
export * from './quantum/povm';
export * from './quantum/kochen_specker_18';
export * from './quantum/bohr_complementarity_engine';
export * from './governance/pac-bayes-bound';
export * from './governance/madhava-bound';
export {
  IDENTITY,
  pack,
  unpack,
  norm,
  multiply,
  conjugate,
  normalize as normalizeQuaternion,
  slerp,
  isApproximatelyUnit,
  type QuaternionState,
} from './governance/quaternion-state';
export * from './governance/lid-check';
export * from './calibration/false-position';
export * from './lambda/composition-ring';
export * from './thresholds/akhmim-table';
export * from './thresholds/quadratic-solver';
