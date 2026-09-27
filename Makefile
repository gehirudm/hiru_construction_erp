.PHONY: start stop sleep status logs seed verify
start stop sleep status logs seed verify:
	@./scripts/dev $@
