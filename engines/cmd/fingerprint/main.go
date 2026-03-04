package main

import (
	"fmt"

	"github.com/Cass-ette/NetKitX/engines/pkg/output"
)

type Params struct {
	Target string `json:"target"`
	Port   int    `json:"port"`
}

func main() {
	var params Params
	if err := output.ReadParams(&params); err != nil {
		output.EmitError(fmt.Errorf("failed to read params: %w", err))
		return
	}

	output.EmitProgress(0, fmt.Sprintf("Fingerprinting %s:%d", params.Target, params.Port))

	// TODO: implement HTTP/TCP fingerprinting
	output.EmitLog("Fingerprint engine not yet implemented")
	output.EmitProgress(100, "Done")
}
