package main

import (
	"fmt"

	"github.com/Cass-ette/NetKitX/engines/pkg/output"
)

type Params struct {
	Domain    string   `json:"domain"`
	Wordlist  string   `json:"wordlist"`
	Resolvers []string `json:"resolvers"`
}

func main() {
	var params Params
	if err := output.ReadParams(&params); err != nil {
		output.EmitError(fmt.Errorf("failed to read params: %w", err))
		return
	}

	output.EmitProgress(0, fmt.Sprintf("Subdomain enumeration for %s", params.Domain))

	// TODO: implement DNS brute-force and passive enumeration
	output.EmitLog("Subdomain engine not yet implemented")
	output.EmitProgress(100, "Done")
}
