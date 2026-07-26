/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/

import LutarPolicy.Action

namespace LutarPolicy

inductive Decision where
  | allow
  | reject
  deriving DecidableEq, Repr

structure Rule where
  principal : Principal
  action : ActionType
  artifactDigest : ArtifactDigest
  environment : Environment
  deriving DecidableEq, Repr

structure PolicyState where
  now : Nat
  version : PolicyVersion
  rules : List Rule
  revokedPrincipals : List Principal
  revokedVersions : List PolicyVersion
  deriving DecidableEq, Repr

def RuleMatches (rule : Rule) (request : Request) : Prop :=
  rule.principal = request.principal ∧
    rule.action = request.action ∧
    rule.artifactDigest = request.artifactDigest ∧
    rule.environment = request.environment

instance (rule : Rule) (request : Request) : Decidable (RuleMatches rule request) :=
  by
    unfold RuleMatches
    infer_instance

def HasMatchingRule (state : PolicyState) (request : Request) : Prop :=
  ∃ rule ∈ state.rules, RuleMatches rule request

instance (state : PolicyState) (request : Request) :
    Decidable (HasMatchingRule state request) :=
  by
    unfold HasMatchingRule
    infer_instance

def evaluate (state : PolicyState) (request : Request) : Decision :=
  if state.revokedPrincipals.contains request.principal then
    .reject
  else if state.revokedVersions.contains state.version then
    .reject
  else if HasMatchingRule state request then
    .allow
  else
    .reject

end LutarPolicy
