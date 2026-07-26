/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/
namespace LutarPolicy

inductive Action where
  | deployStaging
  | deployProduction
  | rotateSecret
  | changeIdentity
  | changePolicy
  | migrateDatabase
  | changeTraffic
  | changeRuleset
  | changeAdmission
  | promoteModel
  | publishBenchmark
  | upgradeClaim
  | destroyInfrastructure
  deriving DecidableEq, Repr

def Action.highRisk : Action → Bool
  | .deployStaging => false
  | _ => true

end LutarPolicy
