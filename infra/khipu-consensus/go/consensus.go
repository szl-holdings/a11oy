// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
//
// Package khipuconsensus is the Go reference implementation of the Khipu
// Consensus protocol — Byzantine-fault-tolerant multi-party signed agreement.
// Each witness ("organ") signs an action hash with its own ECDSA-P256 key over
// the DSSE Pre-Authentication Encoding. >= threshold valid `allow` signatures
// over the same action hash ⇒ CANONICAL. Verifies the same deterministic
// vectors as the Python and TypeScript reference implementations.
package khipuconsensus

import (
	"crypto/ecdsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
)

const OrganVerdictPayloadType = "application/vnd.szl.khipu.organ-verdict+json"

// CanonicalJSON returns deterministic canonical JSON (sorted keys, compact).
func CanonicalJSON(v any) ([]byte, error) {
	// Re-marshal through a generic map/value to enforce sorted keys recursively.
	raw, err := json.Marshal(v)
	if err != nil {
		return nil, err
	}
	var generic any
	if err := json.Unmarshal(raw, &generic); err != nil {
		return nil, err
	}
	var b strings.Builder
	if err := writeCanon(&b, generic); err != nil {
		return nil, err
	}
	return []byte(b.String()), nil
}

func writeCanon(b *strings.Builder, v any) error {
	switch t := v.(type) {
	case map[string]any:
		keys := make([]string, 0, len(t))
		for k := range t {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		b.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				b.WriteByte(',')
			}
			kb, _ := json.Marshal(k)
			b.Write(kb)
			b.WriteByte(':')
			if err := writeCanon(b, t[k]); err != nil {
				return err
			}
		}
		b.WriteByte('}')
	case []any:
		b.WriteByte('[')
		for i, e := range t {
			if i > 0 {
				b.WriteByte(',')
			}
			if err := writeCanon(b, e); err != nil {
				return err
			}
		}
		b.WriteByte(']')
	default:
		enc, err := json.Marshal(t)
		if err != nil {
			return err
		}
		b.Write(enc)
	}
	return nil
}

// PAE computes the DSSE Pre-Authentication Encoding (DSSEv1).
func PAE(payloadType string, body []byte) []byte {
	t := []byte(payloadType)
	out := []byte("DSSEv1 ")
	out = append(out, []byte(strconv.Itoa(len(t)))...)
	out = append(out, ' ')
	out = append(out, t...)
	out = append(out, ' ')
	out = append(out, []byte(strconv.Itoa(len(body)))...)
	out = append(out, ' ')
	out = append(out, body...)
	return out
}

// OrganVerdict is the wire shape of one witness's signed verdict.
type OrganVerdict struct {
	Organ       string `json:"organ"`
	Keyid       string `json:"keyid"`
	PayloadType string `json:"payloadType"`
	Payload     string `json:"payload"`   // base64 canonical statement
	Signature   string `json:"signature"` // base64 ECDSA-P256-SHA256 over PAE
	Verdict     string `json:"verdict"`
	Reason      string `json:"reason"`
}

// OrganCheck is the per-witness verification result.
type OrganCheck struct {
	Organ           string
	Keyid           string
	Valid           bool
	Verdict         string
	ActionHashMatch bool
	Counts          bool
	Reason          string
}

// ConsensusResult is the tally outcome.
type ConsensusResult struct {
	ActionHash      string
	Threshold       int
	N               int
	ConsensusCount  int
	Decision        string // "canonical" | "rejected"
	KhipuConsensus  string
	Checks          []OrganCheck
}

func loadECDSAPublic(pemStr string) (*ecdsa.PublicKey, error) {
	block, _ := pem.Decode([]byte(pemStr))
	if block == nil {
		return nil, errors.New("invalid PEM")
	}
	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return nil, err
	}
	ec, ok := pub.(*ecdsa.PublicKey)
	if !ok {
		return nil, errors.New("not an ECDSA public key")
	}
	return ec, nil
}

// VerifyVerdict verifies one witness signature against its public key + action hash.
func VerifyVerdict(v OrganVerdict, publicKeyPem, actionHash string) OrganCheck {
	chk := OrganCheck{Organ: v.Organ, Keyid: v.Keyid}
	if v.Payload == "" || v.Signature == "" {
		chk.Reason = "missing payload/signature"
		return chk
	}
	body, err := base64.StdEncoding.DecodeString(v.Payload)
	if err != nil {
		chk.Reason = "bad payload b64"
		return chk
	}
	sig, err := base64.StdEncoding.DecodeString(v.Signature)
	if err != nil {
		chk.Reason = "bad signature b64"
		return chk
	}
	pt := v.PayloadType
	if pt == "" {
		pt = OrganVerdictPayloadType
	}
	pub, err := loadECDSAPublic(publicKeyPem)
	if err != nil {
		chk.Reason = err.Error()
		return chk
	}
	digest := sha256.Sum256(PAE(pt, body))
	if !ecdsa.VerifyASN1(pub, digest[:], sig) {
		chk.Reason = "signature mismatch"
		return chk
	}
	var decoded struct {
		ActionHash string `json:"action_hash"`
		Verdict    string `json:"verdict"`
	}
	if err := json.Unmarshal(body, &decoded); err != nil {
		chk.Reason = "bad statement json"
		return chk
	}
	chk.Valid = true
	chk.Verdict = decoded.Verdict
	chk.ActionHashMatch = decoded.ActionHash == actionHash
	chk.Counts = chk.ActionHashMatch && decoded.Verdict == "allow"
	return chk
}

// Tally counts valid+allow signatures over actionHash and applies the BFT threshold.
// A nil entry in verdicts models an abstaining/timed-out witness.
func Tally(actionHash string, verdicts []*OrganVerdict, pubkeys map[string]string, threshold, n int) ConsensusResult {
	checks := make([]OrganCheck, 0, len(verdicts))
	count := 0
	for _, v := range verdicts {
		if v == nil {
			checks = append(checks, OrganCheck{Reason: "abstain/timeout"})
			continue
		}
		pem, ok := pubkeys[v.Organ]
		if !ok {
			checks = append(checks, OrganCheck{Organ: v.Organ, Keyid: v.Keyid, Reason: "no public key"})
			continue
		}
		chk := VerifyVerdict(*v, pem, actionHash)
		checks = append(checks, chk)
		if chk.Counts {
			count++
		}
	}
	decision := "rejected"
	if count >= threshold {
		decision = "canonical"
	}
	return ConsensusResult{
		ActionHash: actionHash, Threshold: threshold, N: n, ConsensusCount: count,
		Decision: decision, KhipuConsensus: fmt.Sprintf("%d-of-%d", count, n), Checks: checks,
	}
}
