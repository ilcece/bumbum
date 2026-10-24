"""用 Windows 作业对象管理本工具的子进程，不按进程名或旧 PID 结束程序。"""

import ctypes
from ctypes import wintypes as w
import os
import subprocess


class WindowsJob:
    """关闭工具或作业句柄时，由系统结束所属进程及其后代。"""

    def __init__(self):
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([w.LPVOID, w.LPCWSTR], w.HANDLE),
            "SetInformationJobObject": ([w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD], w.BOOL),
            "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
            "CloseHandle": ([w.HANDLE], w.BOOL),
            "ResumeThread": ([w.HANDLE], w.DWORD),
            "TerminateProcess": ([w.HANDLE, w.UINT], w.BOOL),
            "GetExitCodeProcess": ([w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
            "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
            "CreateProcessW": ([w.LPCWSTR, w.LPWSTR, w.LPVOID, w.LPVOID, w.BOOL,
                                w.DWORD, w.LPVOID, w.LPCWSTR, w.LPVOID, w.LPVOID], w.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = arguments, result

        class BasicLimits(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                        ("flags", w.DWORD), ("min_set", ctypes.c_size_t),
                        ("max_set", ctypes.c_size_t), ("active", w.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", w.DWORD),
                        ("scheduling", w.DWORD)]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("basic", BasicLimits), ("io", ctypes.c_uint64 * 6),
                        ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                        ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]

        self.handle = self.api.CreateJobObjectW(None, None)
        self.processes = []
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # 最后一个作业句柄关闭时，结束其中的进程。
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def launch(self, arguments, root, log):
        """先暂停创建、加入本作业，再运行，防止子进程提前生成未受管的后代。"""
        import msvcrt

        class StartupInfo(ctypes.Structure):
            _fields_ = [("size", w.DWORD), ("reserved", w.LPWSTR), ("desktop", w.LPWSTR),
                        ("title", w.LPWSTR), ("x", w.DWORD), ("y", w.DWORD),
                        ("width", w.DWORD), ("height", w.DWORD), ("chars_x", w.DWORD),
                        ("chars_y", w.DWORD), ("fill", w.DWORD), ("flags", w.DWORD),
                        ("show", w.WORD), ("reserved_size", w.WORD), ("reserved_ptr", w.LPVOID),
                        ("stdin", w.HANDLE), ("stdout", w.HANDLE), ("stderr", w.HANDLE)]

        class ProcessInfo(ctypes.Structure):
            _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE),
                        ("pid", w.DWORD), ("thread_id", w.DWORD)]

        startup, process = StartupInfo(), ProcessInfo()
        startup.size, startup.flags = ctypes.sizeof(startup), 0x100
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(part) for part in arguments]))
        with open(os.devnull, "rb") as source:
            startup.stdin = msvcrt.get_osfhandle(source.fileno())
            startup.stdout = startup.stderr = msvcrt.get_osfhandle(log.fileno())
            for handle in (startup.stdin, startup.stdout):
                os.set_handle_inheritable(handle, True)
            try:
                # 不开额外控制台；输出写入本机日志，浏览器关闭不会结束服务。
                if not self.api.CreateProcessW(str(arguments[0]), command, None, None, True,
                                               0x4 | 0x08000000, None, str(root),
                                               ctypes.byref(startup), ctypes.byref(process)):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                for handle in (startup.stdin, startup.stdout):
                    os.set_handle_inheritable(handle, False)
        try:
            if not self.api.AssignProcessToJobObject(self.handle, process.process):
                raise ctypes.WinError(ctypes.get_last_error())
            if self.api.ResumeThread(process.thread) == 0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.api.TerminateProcess(process.process, 1)
            self.api.CloseHandle(process.process)
            raise
        finally:
            self.api.CloseHandle(process.thread)
        self.processes.append(process.process)

    def healthy(self):
        for handle in self.processes:
            code = w.DWORD()
            if not self.api.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
                return False
        return True

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None
        for handle in self.processes:
            self.api.WaitForSingleObject(handle, 5000)
            self.api.CloseHandle(handle)
        self.processes.clear()
