/* ARK syscall exports, NIDs = first four SHA-1 bytes of function name, LE. */
    .set noreorder
#include "pspimport.s"
    IMPORT_START "KUBridge",0x40090000
    IMPORT_FUNC "KUBridge",0x4b321167,kuKernelFindModuleByName
    IMPORT_FUNC "KUBridge",0x24331850,kuKernelGetModel
    IMPORT_FUNC "KUBridge",0xb0b8824e,kuKernelInitKeyConfig
    IMPORT_START "SystemCtrlForUser",0x40090000
    IMPORT_FUNC "SystemCtrlForUser",0xb47c9d77,sctrlSEGetVersion
    IMPORT_FUNC "SystemCtrlForUser",0x1090a2e1,sctrlHENGetVersion
    IMPORT_FUNC "SystemCtrlForUser",0x5328b431,sctrlHENGetMinorVersion
