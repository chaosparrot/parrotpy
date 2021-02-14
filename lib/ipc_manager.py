from multiprocessing import shared_memory
import array
import time
import struct

# ----------------- NOTICE -------------------
# THIS FILE IS USED TO ENABLE OTHER PROGRAMS TO INTERACT OR TO READ OUT STATES FROM PARROT.PY
# CHANGE THESE MEMORY ADDRESSES AS LITTLE AS POSSIBLE TO PREVENT ISSUES ARISING
# Currently a single block of 4kb shared memory is used for inter-process communication
# -------------------------------------------

IPC_MAX_MEMLENGTH_STRING = 255
IPC_MEMBLOCK_INPUT = 0
IPC_STATE_PARROTPY_NOT_RUNNING = 0
IPC_STATE_PARROTPY_RUNNING = 1
IPC_STATE_PARROTPY_PAUSED = 2
IPC_STATE_PARROTPY_SWITCHING = 3
IPC_STATE_PARROTPY_STOPPED = 4

# --------- INPUT LOCATIONS ( 0 to 1023 ) ---------
# These memory locations and values can be changed by other programs
# ParrotPy's state will be adjusted accordingly as long as the values are properly adhered to
IPC_MEMLOC_PARROTPY_STATE = IPC_MEMBLOCK_INPUT + 0 # 8bit integer displaying the current parrot py state
IPC_MEMLOC_PARROTPY_NEW_STATE = IPC_MEMBLOCK_INPUT + 1 # 8bit integer displaying the state we want parrot to transition to
IPC_MEMLOC_CLASSIFIER_LENGTH = IPC_MEMBLOCK_INPUT + 2 # 8bit integer of the length of the classifier string
IPC_MEMLOC_CLASSIFIER = IPC_MEMBLOCK_INPUT + 3 # 3 to 257 - UTF8 String contents ( max unicode length of 255 )
IPC_MEMLOC_CURRENT_MODE_LENGTH = IPC_MEMBLOCK_INPUT + 258 # 8bit integer of the length of the current running mode
IPC_MEMLOC_CURRENT_MODE = IPC_MEMBLOCK_INPUT + 259 # 259 to 513 - UTF8 String contents ( max unicode length of 255 )

# ----- INTERACTION LOCATIONS ( 1024 to 2047 ) -----
# These memory locations and values are reserved to send key bindings and inputs to other programs
IPC_MEMBLOCK_INTERACTION = 1024

# ------ OVERLAY LOCATIONS ( 2048 to 3071 ) --------
# These memory locations are used to read out the current state of keys in Parrot.PY
# These values are considered read-only 
IPC_MEMBLOCK_OVERLAY = 2048
IPC_MEMLOC_CTRL_STATE = IPC_MEMBLOCK_OVERLAY + 0 # Ctrl pressed down = 1, else 0
IPC_MEMLOC_SHIFT_STATE = IPC_MEMBLOCK_OVERLAY + 1 # Shift pressed down = 1, else 0
IPC_MEMLOC_ALT_STATE = IPC_MEMBLOCK_OVERLAY + 2 # Alt pressed down = 1, else 0
IPC_MEMLOC_UP_STATE = IPC_MEMBLOCK_OVERLAY + 3 # Up pressed down = 1, else 0
IPC_MEMLOC_DOWN_STATE = IPC_MEMBLOCK_OVERLAY + 4 # Down pressed down = 1, else 0
IPC_MEMLOC_LEFT_STATE = IPC_MEMBLOCK_OVERLAY + 5 # Left pressed down = 1, else 0
IPC_MEMLOC_RIGHT_STATE = IPC_MEMBLOCK_OVERLAY + 6 # Right pressed down = 1, else 0
IPC_MEMLOC_OVERLAY_LENGTH = IPC_MEMBLOCK_OVERLAY + 7 # 8bit integer of the length of overlay filename
IPC_MEMLOC_OVERLAY_FILENAME = IPC_MEMBLOCK_OVERLAY + 8 # 8 to 262 - UTF8 String contents ( max unicode length of 255 )
IPC_MEMLOC_SOUNDNAME_LENGTH = IPC_MEMBLOCK_OVERLAY + 263 # 8bit integer of the length of the sound string
IPC_MEMLOC_SOUNDNAME = IPC_MEMBLOCK_OVERLAY + 264 # 264 to 519 - UTF8 String contents ( max unicode length of 255 )
IPC_MEMLOC_ACTIONNAME_LENGTH = IPC_MEMBLOCK_OVERLAY + 520 # 8bit integer of the length of the action string
IPC_MEMLOC_ACTIONNAME = IPC_MEMBLOCK_OVERLAY + 521 # 521 to 775 - UTF8 String contents ( max unicode length of 255 )
IPC_MEMLOC_ACTION_AMOUNT = IPC_MEMBLOCK_OVERLAY + 776 # 776 to 777 - 16bit integer of the amount of times this action has been repeated

# ------ FREE ALLOCATION ( 3072 to 4095 ) ------
# This block of 1 kilobyte memory can be used to send any state over to ParrotPy from outside programs
# You can use this state dynamically in your models
IPC_MEMBLOCK_FREE_ALLOC = 3072

_shm = None
_buffer = None
try:
    _shm = shared_memory.SharedMemory(create=True, name="parrotpy_ipc", size=4096)
except FileExistsError:
    _shm = shared_memory.SharedMemory(create=False, name="parrotpy_ipc", size=4096)
_buffer = _shm.buf

# A map of all the button states memory locations
_ipc_button_state = {
    'ctrl': IPC_MEMLOC_CTRL_STATE,
    'shift': IPC_MEMLOC_SHIFT_STATE,
    'alt': IPC_MEMLOC_ALT_STATE,
    'up': IPC_MEMLOC_UP_STATE,
    'down': IPC_MEMLOC_DOWN_STATE,
    'left': IPC_MEMLOC_LEFT_STATE,
    'right': IPC_MEMLOC_RIGHT_STATE
}

_ipc_parrotpy_strings_to_state = {
    'not_running': IPC_STATE_PARROTPY_NOT_RUNNING,
    'running': IPC_STATE_PARROTPY_RUNNING,
    'paused': IPC_STATE_PARROTPY_PAUSED,
    'switching': IPC_STATE_PARROTPY_SWITCHING,
    'stopped': IPC_STATE_PARROTPY_STOPPED
}
_ipc_parrotpy_states_to_string = dict((v,k) for k, v in _ipc_parrotpy_strings_to_state.items())

def setParrotState( type ):
    if (type in _ipc_parrotpy_strings_to_state):
        _buffer[IPC_MEMLOC_PARROTPY_STATE] = _ipc_parrotpy_strings_to_state[type]

def getParrotState():
    return _ipc_parrotpy_states_to_string[_buffer[IPC_MEMLOC_PARROTPY_STATE]]

def requestParrotState( type ):
    if (type in _ipc_parrotpy_strings_to_state):
        _buffer[IPC_MEMLOC_PARROTPY_NEW_STATE] = _ipc_parrotpy_strings_to_state[type]

def getRequestedParrotState():
    return _ipc_parrotpy_states_to_string[_buffer[IPC_MEMLOC_PARROTPY_NEW_STATE]] if isStatechangeRequested() else False

def isStatechangeRequested():
    return _buffer[IPC_MEMLOC_PARROTPY_NEW_STATE] != IPC_STATE_PARROTPY_NOT_RUNNING and _buffer[IPC_MEMLOC_PARROTPY_NEW_STATE] != _buffer[IPC_MEMLOC_PARROTPY_STATE]

def setMode( mode_filename ):
    mode_filename_in_bytes = mode_filename.encode('utf-8')
    strlen = len(mode_filename_in_bytes)
    if (strlen > IPC_MAX_MEMLENGTH_STRING):
        print( "Modes can have a maximum of 255 character length filenames")
        return

	# Save the overlay length and the image name at the same time to prevent race conditions
    _buffer[IPC_MEMLOC_CURRENT_MODE_LENGTH:IPC_MEMLOC_CURRENT_MODE + strlen] = bytes([strlen]) + mode_filename_in_bytes

def getMode():
    strlen = _buffer[IPC_MEMLOC_CURRENT_MODE_LENGTH]
    if (strlen > 0):
        return array.array('B', _buffer[IPC_MEMLOC_CURRENT_MODE:IPC_MEMLOC_CURRENT_MODE + strlen]).tobytes().decode('utf-8')    
    else:
        return ""
        
def setClassifier( classifier_name ):
    classifier_name_in_bytes = classifier_name.encode('utf-8')
    strlen = len(classifier_name_in_bytes)
    if (strlen > IPC_MAX_MEMLENGTH_STRING):
        print( "Classifiers can have a maximum of 255 character length filenames")
        return

	# Save the overlay length and the image name at the same time to prevent race conditions
    _buffer[IPC_MEMLOC_CLASSIFIER_LENGTH:IPC_MEMLOC_CLASSIFIER + strlen] = bytes([strlen]) + classifier_name_in_bytes

def getClassifier():
    strlen = _buffer[IPC_MEMLOC_CLASSIFIER_LENGTH]
    if (strlen > 0):
        return array.array('B', _buffer[IPC_MEMLOC_CLASSIFIER:IPC_MEMLOC_CLASSIFIER + strlen]).tobytes().decode('utf-8')    
    else:
        return ""

def setButtonState( button, state ):
    if (button in _ipc_button_state):
        _buffer[_ipc_button_state[button]] = 1 if state > 0 else 0
        
def getButtonState( button ):
    if (button in _ipc_button_state):
        return _buffer[_ipc_button_state[button]] > 0
    else:
        return False

def setOverlayImage( filename ):
    overlayimage_in_bytes = filename.encode('utf-8')
    strlen = len(overlayimage_in_bytes)
    if (strlen > IPC_MAX_MEMLENGTH_STRING):
        print( "Overlay images can have a maximum of 255 character length filenames")
        return

	# Save the overlay length and the image name at the same time to prevent race conditions
    _buffer[IPC_MEMLOC_OVERLAY_LENGTH:IPC_MEMLOC_OVERLAY_FILENAME + strlen] = bytes([strlen]) + overlayimage_in_bytes

def getOverlayImage():
    strlen = _buffer[IPC_MEMLOC_OVERLAY_LENGTH]
    if (strlen > 0):
        return array.array('B', _buffer[IPC_MEMLOC_OVERLAY_FILENAME:IPC_MEMLOC_OVERLAY_FILENAME + strlen]).tobytes().decode('utf-8')    
    else:
        return ""
        
def setSoundName( soundname ):
    soundname_in_bytes = soundname.encode('utf-8')
    strlen = len(soundname_in_bytes)
    if (strlen > IPC_MAX_MEMLENGTH_STRING):
        print( "Sound names can have a maximum of 255 character length")
        return        

	# Save the sound name length and the sound name at the same time to prevent race conditions
    _buffer[IPC_MEMLOC_SOUNDNAME_LENGTH:IPC_MEMLOC_SOUNDNAME + strlen] = bytes([strlen]) + soundname_in_bytes

def getSoundName():
    strlen = _buffer[IPC_MEMLOC_SOUNDNAME_LENGTH]
    if (strlen > 0):
        return array.array('B', _buffer[IPC_MEMLOC_SOUNDNAME:IPC_MEMLOC_SOUNDNAME + strlen]).tobytes().decode('utf-8')    
    else:
        return ""
        
def setActionName( actionname ):
    actionname_in_bytes = actionname.encode('utf-8')
    strlen = len(actionname_in_bytes)
    if (strlen > IPC_MAX_MEMLENGTH_STRING):
        print( "Action names can have a maximum of 255 character length")
        return
    
    total_action_bytes = bytes([strlen]) + actionname_in_bytes + bytes(IPC_MAX_MEMLENGTH_STRING - strlen)
    total_action_length = len(total_action_bytes)
    
    # If the action is the same, increment the amount
    if (_buffer[IPC_MEMLOC_ACTIONNAME_LENGTH:IPC_MEMLOC_ACTIONNAME_LENGTH + total_action_length] == total_action_bytes):
        integeramount = struct.unpack('>H', _buffer[IPC_MEMLOC_ACTION_AMOUNT:IPC_MEMLOC_ACTION_AMOUNT + 2].tobytes())[0] + 1
        intbytes = struct.pack('>H', integeramount)
    else:
        intbytes = struct.pack('>H', 1)
        
	# Save the action name length, the action name and the action amount at the same time to prevent race conditions
    _buffer[IPC_MEMLOC_ACTIONNAME_LENGTH:IPC_MEMLOC_ACTIONNAME_LENGTH + total_action_length + 2] = total_action_bytes + intbytes

def getActionName():
    strlen = _buffer[IPC_MEMLOC_ACTIONNAME_LENGTH]
    if (strlen > 0):
        return array.array('B', _buffer[IPC_MEMLOC_ACTIONNAME:IPC_MEMLOC_ACTIONNAME + strlen]).tobytes().decode('utf-8')    
    else:
        return ""
        
def getActionAmount():
    return struct.unpack('>H', _buffer[IPC_MEMLOC_ACTION_AMOUNT:IPC_MEMLOC_ACTION_AMOUNT + 2])[0]