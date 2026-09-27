.PHONY: start stop sleep status logs seed verify test test-ui
start stop sleep status logs seed verify test test-ui:
	@./scripts/dev $@
