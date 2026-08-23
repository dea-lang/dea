L1C ?= l1c

PROJECT_ROOT := .
BUILD_DIR := build
PROGRAM := $(BUILD_DIR)/main
AUX_OBJECT := $(BUILD_DIR)/aux.o
AUX_INTERFACE := $(BUILD_DIR)/aux.l1m

.PHONY: all run clean

all: $(PROGRAM)

$(BUILD_DIR):
	mkdir -p "$@"

# A multi-target pattern rule keeps each .o and .l1m pair together and works
# with GNU Make 3.81.
$(BUILD_DIR)/%.o $(BUILD_DIR)/%.l1m: %.l1 Makefile | $(BUILD_DIR)
	$(L1C) --compile "$*" -Rp "$(PROJECT_ROOT)" -I "$(BUILD_DIR)" -o "$(BUILD_DIR)/$*.o"

$(PROGRAM): main.l1 $(AUX_OBJECT) $(AUX_INTERFACE) Makefile | $(BUILD_DIR)
	$(L1C) --build main -Rp "$(PROJECT_ROOT)" -I "$(BUILD_DIR)" -o "$@"

run: $(PROGRAM)
	"$(PROGRAM)"

clean:
	rm -f "$(PROGRAM)" "$(AUX_OBJECT)" "$(AUX_INTERFACE)"
	rmdir "$(BUILD_DIR)" 2>/dev/null || true
