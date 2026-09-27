.PHONY: start stop sleep status logs seed verify test
start stop sleep status logs seed verify test:
	@./scripts/dev $@
