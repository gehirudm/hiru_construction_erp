.PHONY: start stop sleep status logs seed verify test test-ui test-team
start stop sleep status logs seed verify test test-ui test-team:
	@./scripts/dev $@
