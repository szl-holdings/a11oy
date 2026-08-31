# a11oy policy gate: deployment_readiness
# controls: ISO27001/8.25, NIST80053/CM-3, ISO42001/A.6.7
# bundle digest (whole bundle): sha256:4b035da9e752dcdb81c8390974752fc729da8192e60a0459de50a05d4c9563ba

package a11oy.gates.deployment_readiness

# Block model promotion unless the signed package digest + Λ floor are met.
default promote := false

promote {
  input.package_signed == true
  input.slsa_level >= 2
  input.lambda_score >= input.lambda_promote_floor
}
