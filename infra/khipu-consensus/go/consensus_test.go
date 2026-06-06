// SPDX-License-Identifier: Apache-2.0
package khipuconsensus

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

type vectorFile struct {
	ActionHash string            `json:"action_hash"`
	Threshold  int               `json:"threshold"`
	N          int               `json:"n"`
	Pubkeys    map[string]string `json:"pubkeys"`
	Cases      []struct {
		Name   string `json:"name"`
		Expect struct {
			Decision       string `json:"decision"`
			ConsensusCount int    `json:"consensus_count"`
		} `json:"expect"`
		Signatures []*OrganVerdict `json:"signatures"`
	} `json:"cases"`
}

func TestVectors(t *testing.T) {
	path := filepath.Join("..", "testdata", "vectors.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read vectors: %v", err)
	}
	var vf vectorFile
	if err := json.Unmarshal(raw, &vf); err != nil {
		t.Fatalf("parse vectors: %v", err)
	}
	for _, c := range vf.Cases {
		r := Tally(vf.ActionHash, c.Signatures, vf.Pubkeys, vf.Threshold, vf.N)
		if r.Decision != c.Expect.Decision || r.ConsensusCount != c.Expect.ConsensusCount {
			t.Errorf("[FAIL] %s: got %s %s, want %s %d-of-%d", c.Name, r.KhipuConsensus,
				r.Decision, c.Expect.Decision, c.Expect.ConsensusCount, vf.N)
		} else {
			t.Logf("[PASS] %s: %s -> %s", c.Name, r.KhipuConsensus, r.Decision)
		}
	}
}
