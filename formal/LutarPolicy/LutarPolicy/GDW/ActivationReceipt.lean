/-
SPDX-License-Identifier: Apache-2.0
Copyright 2026 Stephen P. Lutar Jr.
-/

import LutarPolicy.GDW.SchedulerSoundness

namespace LutarPolicy.GDW

structure ActivationReceipt where
  before : State
  after : State
  decision : Decision
  schedulerMode : SchedulerMode
  payloadDigest : String
  deriving DecidableEq, Repr

def receiptFor
    (decision : Decision)
    (mode : SchedulerMode)
    (before : State)
    (nextDigest : String) : ActivationReceipt :=
  {
    before := before
    after := transition decision before nextDigest
    decision := decision
    schedulerMode := mode
    payloadDigest := nextDigest
  }

theorem rejected_receipt_preserves_state
    (mode : SchedulerMode) (before : State) (nextDigest : String) :
    (receiptFor .reject mode before nextDigest).after = before := by
  rfl

end LutarPolicy.GDW
