TARGET = battery_level
SOURCE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
ifeq ($(origin CFLAGS),command line)
$(error CFLAGS overrides are unsupported)
endif
ifeq ($(origin OBJS),command line)
$(error OBJS overrides are unsupported)
endif
DIAGNOSTICS ?= 0
ifneq ($(DIAGNOSTICS),0)
ifneq ($(DIAGNOSTICS),1)
$(error DIAGNOSTICS must be 0 or 1)
endif
endif
ifeq ($(VSH_PAYLOAD),)
$(error VSH_PAYLOAD must name the verified user PRX)
endif
OBJS = main.o vsh.o payload.o home_backend.o home_callback.o home_hook.o assets.o sprite.o pgf.o power_worker.o support.o
ifeq ($(DIAGNOSTICS),1)
OBJS += diagnostics.o
endif
BUILD_PRX = 1
PRX_EXPORTS = exports.exp
USE_KERNEL_LIBS = 1
PSP_FW_VERSION = 661
CFLAGS = -std=c99 -O2 -G0 -Wall -Wextra -Werror -ffreestanding -fno-builtin -fno-tree-loop-distribute-patterns
CFLAGS += -DBATTERY_DIAGNOSTICS=$(DIAGNOSTICS)
ASFLAGS = $(CFLAGS)
LDFLAGS = -nostartfiles
LIBS = -lpspsystemctrl_kernel -lpspinit_kernel_660 -lpspsysmem_kernel_660 -lpsploadcore_kernel_660 -lpspthreadman_kernel_660 -lpspinterruptmanager_kernel_660 -lpspmodulemgr_kernel_660 -lpsppower_driver -lgcc
ifeq ($(DIAGNOSTICS),1)
LIBS += -lpspusb_driver
endif
PSPSDK := $(shell psp-config --pspsdk-path)
include $(PSPSDK)/lib/build.mak
.PHONY: FORCE
$(OBJS): FORCE
main.o: $(SOURCE_DIR)main.c FORCE
vsh.o: $(SOURCE_DIR)vsh.c FORCE
diagnostics.o: $(SOURCE_DIR)diagnostics.c FORCE
main.o vsh.o diagnostics.o:
	$(COMPILE.c) $(filter %.c,$^) -o $@
payload.o: $(SOURCE_DIR)payload.S $(VSH_PAYLOAD) FORCE
	$(COMPILE.S) -DVSH_PAYLOAD='"$(VSH_PAYLOAD)"' $< -o $@
home_backend.o: $(SOURCE_DIR)../home/backend.c FORCE
home_callback.o: $(SOURCE_DIR)../home/callback.c FORCE
assets.o: $(SOURCE_DIR)../home/assets.c FORCE
sprite.o: $(SOURCE_DIR)../home/sprite.c FORCE
pgf.o: $(SOURCE_DIR)../home/pgf.c FORCE
power_worker.o: $(SOURCE_DIR)../home/power_worker.c FORCE
support.o: $(SOURCE_DIR)support.c FORCE
home_backend.o home_callback.o assets.o sprite.o pgf.o power_worker.o support.o:
	$(COMPILE.c) $(filter %.c,$^) -o $@
# The binary checker requires the original complete instruction sequence/ABI.
home_hook.o: $(SOURCE_DIR)../home/hook.S FORCE
	$(COMPILE.S) $< -o $@
exports.c: $(SOURCE_DIR)exports.exp FORCE
	psp-build-exports -b $< > $@
exports.o: exports.c FORCE
	$(COMPILE.c) $< -o $@
