TARGET = battery_level
SOURCE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
ifneq ($(words $(MAKEFILE_LIST)),1)
$(error Native SDK builds require paths without spaces; use the Docker wrapper)
endif
ifeq ($(origin CFLAGS),command line)
$(error CFLAGS overrides are unsupported; use the fixed verified build flags)
endif
ifeq ($(origin OBJS),command line)
$(error OBJS overrides are unsupported)
endif
INCDIR = $(SOURCE_DIR)
DIAGNOSTICS ?= 0
ifneq ($(DIAGNOSTICS),0)
ifneq ($(DIAGNOSTICS),1)
$(error DIAGNOSTICS must be 0 or 1)
endif
endif
OBJS = main.o xmb.o native.o abi.o ark-imports.o
ifeq ($(DIAGNOSTICS),1)
OBJS += diagnostics.o
endif
BUILD_PRX = 1
PRX_EXPORTS = exports.exp
PSP_FW_VERSION = 661
CFLAGS = -O2 -G0 -Wall -Wextra -Werror -ffreestanding -fno-builtin -DBATTERY_DIAGNOSTICS=$(DIAGNOSTICS)
ASFLAGS = $(CFLAGS)
LDFLAGS = -nostartfiles
LIBS = -lpsppower -lpspusb
PSPSDK := $(shell psp-config --pspsdk-path)
include $(PSPSDK)/lib/build.mak

# A mode switch must rebuild every object: Status has a different layout and
# release must never reuse a diagnostic object with filesystem imports.
.PHONY: FORCE
$(OBJS): FORCE
main.o xmb.o native.o diagnostics.o: $(addprefix $(SOURCE_DIR),xmb.h native.h diagnostics.h)
xmb.o: $(addprefix $(SOURCE_DIR),layout_policy.h recovery_policy.h update_policy.h)
%.o: $(SOURCE_DIR)%.c FORCE
	$(COMPILE.c) $< -o $@
%.o: $(SOURCE_DIR)%.S FORCE
	$(COMPILE.S) $< -o $@
exports.c: $(SOURCE_DIR)exports.exp FORCE
	psp-build-exports -b $< > $@
exports.o: exports.c FORCE
	$(COMPILE.c) $< -o $@
