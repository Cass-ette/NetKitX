// Package output provides a unified JSON event format for all Go engines.
// Each engine writes one JSON line per event to stdout.
package output

import (
	"encoding/json"
	"fmt"
	"os"
)

type Event struct {
	Type string      `json:"type"` // "progress", "result", "error", "log"
	Data interface{} `json:"data"`
}

func EmitProgress(percent int, msg string) {
	emit(Event{Type: "progress", Data: map[string]interface{}{"percent": percent, "msg": msg}})
}

func EmitResult(data interface{}) {
	emit(Event{Type: "result", Data: data})
}

func EmitError(err error) {
	emit(Event{Type: "error", Data: map[string]string{"error": err.Error()}})
}

func EmitLog(msg string) {
	emit(Event{Type: "log", Data: map[string]string{"msg": msg}})
}

func emit(e Event) {
	b, err := json.Marshal(e)
	if err != nil {
		fmt.Fprintf(os.Stderr, "marshal error: %v\n", err)
		return
	}
	fmt.Println(string(b))
}

// ReadParams reads JSON params from stdin.
func ReadParams(v interface{}) error {
	return json.NewDecoder(os.Stdin).Decode(v)
}
