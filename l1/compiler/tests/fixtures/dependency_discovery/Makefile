# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#
# Caller-owned example using GNU Make >= 4.3. The outer driver locks, scans,
# validates and writes configuration before this Makefile schedules native work.

.DEFAULT_GOAL := all

# Keep path quotes and native Windows backslashes literal in the recipe shell.
DEA_SHELL_QUOTE = '$(subst ','"'"',$(1))'

ifeq ($(DEA_INNER),1)
include $(DEA_FRAGMENT)

# The adapter supplies shell-quoted source, primary object, and canonical module
# arguments. Canonical names retain dotted identity with the same ordered roots.
define DEA_COMPILE
$(call DEA_SHELL_QUOTE,$(PYTHON)) $(call DEA_SHELL_QUOTE,$(DEA_PROJECT_DRIVER)) record $(call DEA_SHELL_QUOTE,$(DEA_ACTION_LOG)) compile $(2) $(1)
$(call DEA_SHELL_QUOTE,$(L1C)) --compile $(3) $(DEA_INPUT_FLAGS) -I $(call DEA_SHELL_QUOTE,$(DEA_ARTIFACT_ROOT)) $(DEA_NATIVE_FLAGS) -o $(2)
endef

.PHONY: all
all: $(DEA_EXECUTABLE)

$(DEA_EXECUTABLE): $(DEA_LINK_DEPS) $(DEA_CONFIG_STAMP) $(DEA_NATIVE_LINK_DEPS)
	$(call DEA_SHELL_QUOTE,$(PYTHON)) $(call DEA_SHELL_QUOTE,$(DEA_PROJECT_DRIVER)) record $(call DEA_SHELL_QUOTE,$(DEA_ACTION_LOG)) link $(call DEA_SHELL_QUOTE,$@)
	$(call DEA_SHELL_QUOTE,$(L1C)) --link $(DEA_OBJECT_ARGS) $(DEA_LINK_INPUT_FLAGS) -I $(call DEA_SHELL_QUOTE,$(DEA_ARTIFACT_ROOT)) $(DEA_LINK_NATIVE_FLAGS) --entry $(call DEA_SHELL_QUOTE,$(DEA_ENTRY)) $(DEA_FOREIGN_FLAGS) -o $(call DEA_SHELL_QUOTE,$@)
else
.PHONY: all
all:
	$(call DEA_SHELL_QUOTE,$(PYTHON)) $(call DEA_SHELL_QUOTE,$(DEA_PROJECT_DRIVER)) build $(call DEA_SHELL_QUOTE,$(DEA_PROJECT_CONFIG))
endif
