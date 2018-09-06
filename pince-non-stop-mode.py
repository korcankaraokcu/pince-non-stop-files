# Old codes that'll be used again when pince-non-stop-mode gets reworked&implemented


#!/usr/bin/python3
from re import search, split, findall
from threading import Lock, Thread
from time import sleep
import pexpect
import os
import ctypes
import struct

libc = ctypes.CDLL('libc.so.6')
is_32bit = struct.calcsize("P") * 8 == 32

import SysUtils
import type_defs

COMBOBOX_BYTE = type_defs.COMBOBOX_BYTE
COMBOBOX_2BYTES = type_defs.COMBOBOX_2BYTES
COMBOBOX_4BYTES = type_defs.COMBOBOX_4BYTES
COMBOBOX_8BYTES = type_defs.COMBOBOX_8BYTES
COMBOBOX_FLOAT = type_defs.COMBOBOX_FLOAT
COMBOBOX_DOUBLE = type_defs.COMBOBOX_DOUBLE
COMBOBOX_STRING = type_defs.COMBOBOX_STRING
COMBOBOX_AOB = type_defs.COMBOBOX_AOB

currentpid = 0
child = object  # this object will be used with pexpect operations
codes_injected = False

infinite_thread_location = str  # location of the injected thread that runs forever at background
infinite_thread_id = str  # id of the injected thread that runs forever at background
lock = Lock()

index_to_gdbcommand_dict = type_defs.index_to_gdbcommand_dict


# The comments next to the regular expressions shows the expected gdb output, an elucidating light for the future developers


# issues the command sent
def send_command(command):
    global child
    with lock:
        child.sendline(command)
        child.expect_exact("(gdb) ")
        output = split(r"&\".*\\n\"", child.before, 1)[1]  # &"command\n"
        print(child.before)  # debug mode on!
        # print(output)
        return output


# check if we can attach to the target
def can_attach(pid=str):
    result = libc.ptrace(16, int(pid), 0, 0)  # 16 is PTRACE_ATTACH, check ptrace.h for details
    if result is -1:
        return False
    os.waitpid(int(pid), 0)
    libc.ptrace(17, int(pid), 0, 17)  # 17 is PTRACE_DETACH, check ptrace.h for details
    sleep(0.01)
    return True

def state_observe_thread():

# Attaches gdb to the target pid
# Returns False if the thread injection fails, True otherwise
# Also saves the injected thread's location and ID as strings, then switches to that thread and stops it
def attach(pid=str, injection_method=0):
    global currentpid
    global child
    global infinite_thread_location
    global infinite_thread_id
    global codes_injected
    SysUtils.create_PINCE_IPC_PATH(pid)
    currentdir = SysUtils.get_current_script_directory()
    child = pexpect.spawnu('sudo LC_NUMERIC=C gdb --interpreter=mi', cwd=currentdir)
    child.setecho(False)
    child.logfile=open(SysUtils.get_gdb_async_file(pid),"w")

    # a creative and meaningful number for such a marvelous and magnificent program PINCE is
    child.timeout = 900000
    child.expect_exact("(gdb)")

    # gdb scripts needs to know PINCE directory, unfortunately they don't start from the place where script exists
    send_command('set $PINCE_PATH=' + '"' + currentdir + '"')
    send_command("source gdb_python_scripts/GDBCommandExtensions.py")
    if injection_method is 1:  # linux-inject
        codes_injected = inject_with_linux_inject(pid)
    send_command("attach " + pid + " &")
    send_command("interrupt")
    currentpid = int(pid)
    if injection_method is 0:  # simple dlopen call
        injectionpath = currentdir + "/Injection/InitialCodeInjections.so"
        codes_injected = inject_with_dlopen_call(injectionpath)
    if codes_injected:
        # address_table_update_thread = PINCE.UpdateAddressTable(pid)  # planned for future
        # address_table_update_thread.start()
        result = send_command("call inject_infinite_thread()")
        filtered_result = search(r"New Thread\s*0x\w+", result)  # New Thread 0x7fab41ffb700 (LWP 7944)
        send_command("c &")

        # Return True if the injection is successful, False if not
        if not filtered_result:
            return False
        threadaddress = split(" ", filtered_result.group(0))[-1]
        match_from_info_threads = search(r"\d+\s*Thread\s*" + threadaddress,
                                         send_command("info threads")).group(0)  # 1 Thread 0x7fab41ffb700
        infinite_thread_id = split(" ", match_from_info_threads)[0]
        infinite_thread_location = threadaddress
        send_command("thread " + infinite_thread_id)
        send_command("interrupt")
        # send_command("call inject_table_update_thread()")  # planned for future
    else:
        send_command("source gdb_python_scripts/on_code_injection_failure")
        send_command("c &")
    return codes_injected


# Farewell...
def detach():
    global child
    global currentpid
    global codes_injected
    #abort_file = type_defs.PINCE_IPC_PATH + str(currentpid) + "/abort.txt"
    #try:
    #    open(abort_file, "w").close()
    #    SysUtils.fix_path_permissions(abort_file)                 # planned for future
    #except:
    #    pass
    child.sendline("q")
    currentpid = 0
    child.close()
    codes_injected = False


# Injects a thread that runs forever at the background, it'll be used to execute GDB commands on
# FIXME: linux-inject is insufficient for big games, it makes big titles such as Torchlight to segfault
def inject_with_linux_inject(pid=str):
    scriptdirectory = SysUtils.get_current_script_directory()
    injectionpath = scriptdirectory + "/Injection/InitialCodeInjections.so"
    if is_32bit:
        result = pexpect.run("sudo ./inject32 -p " + pid + " " + injectionpath, cwd=scriptdirectory + "/linux-inject")
    else:
        result = pexpect.run("sudo ./inject -p " + pid + " " + injectionpath, cwd=scriptdirectory + "/linux-inject")
    print(result)  # for debug
    if search(b"successfully injected", result):  # literal string
        return True
    return False


# variant of inject_with_linux_inject
def inject_with_dlopen_call(library_path):
    injectionpath = '"' + library_path + '"'
    result = send_command("call dlopen(" + injectionpath + ", 1)")
    filtered_result = search(r"\$\d+\s*=\s*\-*\d+", result)  # $1 = -1633996800
    if filtered_result:
        dlopen_return_value = split(" ", filtered_result.group(0))[-1]
        if dlopen_return_value is "0":
            result = send_command("call __libc_dlopen_mode(" + injectionpath + ", 1)")
            filtered_result = search(r"\$\d+\s*=\s*\-*\d+", result)  # $1 = -1633996800
            if filtered_result:
                dlopen_return_value = split(" ", filtered_result.group(0))[-1]
                if dlopen_return_value is "0":
                    return False
                return True
            return False
        return True
    result = send_command("call __libc_dlopen_mode(" + injectionpath + ", 1)")
    filtered_result = search(r"\$\d+\s*=\s*\-*\d+", result)  # $1 = -1633996800
    if filtered_result:
        dlopen_return_value = split(" ", filtered_result.group(0))[-1]
        if dlopen_return_value is "0":
            return False
        return True
    return False


# return a string corresponding to the selected index
# returns "out of bounds" string if the index doesn't match the dictionary
def valuetype_to_gdbcommand(index=int):
    return index_to_gdbcommand_dict.get(index, "out of bounds")


def check_for_restricted_gdb_symbols(string):
    if string is "":
        return True
    if search(r"\".*\"", string) or search(r"\{.*\}", string):  # For string and array expressions
        return False
    if search(r'\$|\s', string):  # These characters make gdb show it's value history, so they should be avoided
        return True
    return False


# returns the value of the expression if it is valid, return the string "??" if not
# this function is mainly used for display in AddAddressManually dialog
# this function also can read symbols such as "_start", "malloc", "printf" and "scanf" as addresses
# typeofaddress is derived from valuetype_to_gdbcommand
# length parameter only gets passed when reading strings or array of bytes
# unicode and zero_terminate parameters are only for strings
# if you just want to get the value of an address, use the function read_value_from_single_address() instead
def read_single_address(address, typeofaddress, length=None, is_unicode=False, zero_terminate=True):
    if check_for_restricted_gdb_symbols(address):
        return "??"
    if length is "":
        return "??"
    if typeofaddress is COMBOBOX_AOB:
        typeofaddress = valuetype_to_gdbcommand(typeofaddress)
        try:
            expectedlength = str(int(length))  # length must be a legit number, so had to do this trick
        except:
            return "??"
        result = send_command("x/" + expectedlength + typeofaddress + " " + address)
        filteredresult = findall(r"\\t0x[0-9a-fA-F]+", result)  # 0x40c431:\t0x31\t0xed\t0x49\t...
        if filteredresult:
            returned_string = ''.join(filteredresult)  # combine all the matched results
            return returned_string.replace(r"\t0x", " ")
        return "??"
    elif typeofaddress is COMBOBOX_STRING:
        typeofaddress = valuetype_to_gdbcommand(typeofaddress)
        if not is_unicode:
            try:
                expectedlength = str(int(length))
            except:
                return "??"
            result = send_command("x/" + expectedlength + typeofaddress + " " + address)
        else:
            try:
                expectedlength = str(int(length) * 2)
            except:
                return "??"
            result = send_command("x/" + expectedlength + typeofaddress + " " + address)
        filteredresult = findall(r"\\t0x[0-9a-fA-F]+", result)  # 0x40c431:\t0x31\t0xed\t0x49\t...
        if filteredresult:
            filteredresult = ''.join(filteredresult)
            returned_string = filteredresult.replace(r"\t0x", "")
            if not is_unicode:
                returned_string = bytes.fromhex(returned_string).decode("ascii", "replace")
            else:
                returned_string = bytes.fromhex(returned_string).decode("utf-8", "replace")
            if zero_terminate:
                if returned_string.startswith('\x00'):
                    returned_string = '\x00'
                else:
                    returned_string = returned_string.split('\x00')[0]
            return returned_string[0:int(length)]
        return "??"
    else:
        typeofaddress = valuetype_to_gdbcommand(typeofaddress)
        result = send_command("x/" + typeofaddress + " " + address)
        filteredresult = search(r":\\t[0-9a-fA-F-,]+", result)  # 0x400000:\t1,3961517377359369e-309
        if filteredresult:
            return split("t", filteredresult.group(0))[-1]
        return "??"


# This function is the same with the read_single_address but it reads values from proc/pid/maps instead
# This function is usable even when thread injection fails but it's more primitive than read_single_address
# Use this if you only want to read some values from an address
# If you want PINCE to parse expressions, use read_single_address instead
def read_value_from_single_address(address, typeofaddress, length, unicode, zero_terminate):
    readed = send_command(
        "pince-read-single-address " + str(address) + "," + str(typeofaddress) + "," + str(length) + "," + str(
            unicode) + "," + str(zero_terminate))
    result = search(r"~\".*\\n\"", readed).group(0)  # ~"result\n"
    result = split(r'\"', result)[1]  # result\n"
    result = split(r"\\", result)[0]  # result

    # check ReadSingleAddress class in GDBCommandExtensions.py to understand why do we separate this parsing from others
    if typeofaddress is COMBOBOX_STRING:
        returned_string = result.replace(" ", "")
        if not unicode:
            returned_string = bytes.fromhex(returned_string).decode("ascii", "replace")
        else:
            returned_string = bytes.fromhex(returned_string).decode("utf-8", "replace")
        if zero_terminate:
            if returned_string.startswith('\x00'):
                returned_string = '\x00'
            else:
                returned_string = returned_string.split('\x00')[0]
        return returned_string[0:int(length)]
    return result


# Converts the given address to symbol if any symbol exists for it
# TODO: Implement a loop-version
def convert_address_to_symbol(string):
    if check_for_restricted_gdb_symbols(string):
        return string
    result = send_command("x/x " + string)
    filteredresult = search(r"<.+>:\\t", result)  # 0x40c435 <_start+4>:\t0x89485ed1\n
    if filteredresult:
        return split(">:", filteredresult.group(0))[0].split("<")[1]
    return string


# Converts the given symbol to address if symbol is valid
# TODO: Implement a loop-version
def convert_symbol_to_address(string):
    if check_for_restricted_gdb_symbols(string):
        return string
    result = send_command("x/x " + string)
    filteredresult = search(r"0x[0-9a-fA-F]+\s+<.+>:\\t", result)  # 0x40c435 <_start+4>:\t0x89485ed1\n
    if filteredresult:
        return split(" ", filteredresult.group(0))[0]
    else:
        filteredresult = search(r"0x[0-9a-fA-F]+:\\t", result)  # 0x1f58010:\t0x00647361\n
        if filteredresult:
            return split(":", filteredresult.group(0))[0]
    return string


def test():
    for x in range(0, 10):
        print(send_command('x/x _start'))


def test2():
    for x in range(0, 10):
        print(send_command("disas /r 0x00400000,+10"))


def test3():
    global child
    while True:
        sleep(1)
        print(child.stdout)
