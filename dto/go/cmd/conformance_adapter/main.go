package main

import (
	"encoding/json"
	"fmt"
	"os"

	dto "reasonscript.org/dto"
)

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: conformance_adapter <reason-ir.json>")
		os.Exit(2)
	}
	input, err := os.ReadFile(os.Args[1])
	if err != nil {
		panic(err)
	}
	var value dto.ReasonIR
	if err := json.Unmarshal(input, &value); err != nil {
		panic(err)
	}
	if value.SchemaVersion != "reason-ir/0.1" {
		fmt.Fprintln(os.Stderr, "unsupported ABI version")
		os.Exit(1)
	}
	ids := map[string]bool{}
	for _, transition := range value.Transitions {
		if ids[transition.TransitionID] || transition.ExpectedCost < 0 {
			fmt.Fprintln(os.Stderr, "invalid transition")
			os.Exit(1)
		}
		ids[transition.TransitionID] = true
	}
	output, err := json.Marshal(value)
	if err != nil {
		panic(err)
	}
	fmt.Println(string(output))
}
