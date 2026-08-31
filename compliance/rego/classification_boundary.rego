# a11oy policy gate: classification_boundary
# controls: ISO42001/A.9.6, NIST80053/AC-3, EUAIAct/Art.14
# bundle digest (whole bundle): sha256:4b035da9e752dcdb81c8390974752fc729da8192e60a0459de50a05d4c9563ba

package a11oy.gates.classification_boundary

# DENY when output classification exceeds the operator's clearance level.
default allow := false

deny[msg] {
  input.output_classification > input.user_clearance_level
  msg := sprintf("output classification %v exceeds user clearance %v",
                 [input.output_classification, input.user_clearance_level])
}

allow {
  count(deny) == 0
}
