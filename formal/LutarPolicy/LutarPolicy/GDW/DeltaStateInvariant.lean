/-
SPDX-License-Identifier: Apache-2.0
Copyright 2026 Stephen P. Lutar Jr.
-/

namespace LutarPolicy.GDW

def deltaUpdate (state : List alpha) (update : alpha -> beta) : List beta :=
  state.map update

theorem delta_update_shape_preserved
    (state : List alpha) (update : alpha -> beta) :
    (deltaUpdate state update).length = state.length := by
  simp [deltaUpdate]

end LutarPolicy.GDW
