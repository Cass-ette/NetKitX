.PHONY: build clean all

BINDIR := bin

all: build

build:
	@mkdir -p $(BINDIR)
	go build -o $(BINDIR)/portscan ./cmd/portscan
	go build -o $(BINDIR)/subdomain ./cmd/subdomain
	go build -o $(BINDIR)/fingerprint ./cmd/fingerprint
	@echo "Built all engines to $(BINDIR)/"

clean:
	rm -rf $(BINDIR)
