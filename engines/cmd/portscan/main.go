package main

import (
	"fmt"
	"net"
	"sync"
	"time"

	"github.com/Cass-ette/NetKitX/engines/pkg/output"
)

type Params struct {
	Target  string `json:"target"`
	Ports   string `json:"ports"`
	Timeout int    `json:"timeout"` // ms per port
	Workers int    `json:"workers"`
}

type PortResult struct {
	Host    string `json:"host"`
	Port    int    `json:"port"`
	State   string `json:"state"`
	Service string `json:"service"`
}

func main() {
	var params Params
	if err := output.ReadParams(&params); err != nil {
		output.EmitError(fmt.Errorf("failed to read params: %w", err))
		return
	}

	if params.Timeout == 0 {
		params.Timeout = 1000
	}
	if params.Workers == 0 {
		params.Workers = 100
	}

	ports := parsePorts(params.Ports)
	total := len(ports)

	output.EmitProgress(0, fmt.Sprintf("Scanning %s (%d ports)", params.Target, total))

	var wg sync.WaitGroup
	sem := make(chan struct{}, params.Workers)
	var mu sync.Mutex
	scanned := 0

	for _, port := range ports {
		wg.Add(1)
		sem <- struct{}{}
		go func(p int) {
			defer wg.Done()
			defer func() { <-sem }()

			addr := fmt.Sprintf("%s:%d", params.Target, p)
			conn, err := net.DialTimeout("tcp", addr, time.Duration(params.Timeout)*time.Millisecond)
			if err == nil {
				conn.Close()
				output.EmitResult(PortResult{
					Host:    params.Target,
					Port:    p,
					State:   "open",
					Service: guessService(p),
				})
			}

			mu.Lock()
			scanned++
			pct := scanned * 100 / total
			if scanned%100 == 0 || scanned == total {
				output.EmitProgress(pct, fmt.Sprintf("Scanned %d/%d ports", scanned, total))
			}
			mu.Unlock()
		}(port)
	}

	wg.Wait()
	output.EmitProgress(100, "Scan complete")
}

func parsePorts(s string) []int {
	if s == "" {
		s = "1-1024"
	}
	var ports []int
	var start, end int
	if _, err := fmt.Sscanf(s, "%d-%d", &start, &end); err == nil {
		for i := start; i <= end; i++ {
			ports = append(ports, i)
		}
	}
	return ports
}

func guessService(port int) string {
	services := map[int]string{
		21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
		80: "http", 110: "pop3", 143: "imap", 443: "https", 445: "smb",
		993: "imaps", 995: "pop3s", 3306: "mysql", 3389: "rdp",
		5432: "postgresql", 6379: "redis", 8080: "http-proxy", 8443: "https-alt",
		27017: "mongodb",
	}
	if s, ok := services[port]; ok {
		return s
	}
	return ""
}
