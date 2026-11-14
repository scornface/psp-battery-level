"""Host ABI for the maintained private-buffer composer, not Sony structures."""
import ctypes


class Tiles(ctypes.Structure):
    _fields_=[('pixels',(ctypes.c_uint16*240)*11),('left',ctypes.c_uint*11),
              ('right',ctypes.c_uint*11),('ready',ctypes.c_uint)]


class Sprite(ctypes.Structure):
    _fields_=[('pixels',ctypes.c_uint16*960),('width',ctypes.c_uint),('height',ctypes.c_uint),
              ('percent',ctypes.c_uint)]


def load_library(path):
    lib=ctypes.CDLL(str(path))
    lib.home_tiles_prepare.argtypes=[ctypes.POINTER(Tiles),ctypes.POINTER(ctypes.c_uint16),ctypes.c_size_t,
                                    ctypes.POINTER(ctypes.c_ubyte),ctypes.c_uint,ctypes.c_uint]
    lib.home_sprite_compose.argtypes=[ctypes.POINTER(Tiles),ctypes.c_uint,ctypes.POINTER(Sprite)]
    return lib
