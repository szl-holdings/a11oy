/-
SPDX-License-Identifier: Apache-2.0
Copyright 2026 Stephen P. Lutar Jr.
-/

import LutarPolicy.GDW.ActivationReceipt

namespace LutarPolicy.GDW

def replay (receipt : ActivationReceipt) : State :=
  transition receipt.decision receipt.before receipt.payloadDigest

theorem activation_receipt_replayable
    (decision : Decision)
    (mode : SchedulerMode)
    (before : State)
    (nextDigest : String) :
    replay (receiptFor decision mode before nextDigest) =
      transition decision before nextDigest := by
  rfl

end LutarPolicy.GDW
