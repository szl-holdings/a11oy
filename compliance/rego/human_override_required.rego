# a11oy policy gate: human_override_required
# controls: ISO42001/A.9.3, ISO42001/A.4.6, NIST80053/AU-2, EUAIAct/Art.14
# bundle digest (whole bundle): sha256:4b035da9e752dcdb81c8390974752fc729da8192e60a0459de50a05d4c9563ba

package a11oy.gates.human_override_required

# Require a human override for irreversible actions or when Λ < threshold.
default require_human := false

require_human {
  input.action_class == "irreversible"
}

require_human {
  input.lambda_score < input.lambda_halt_threshold
}
