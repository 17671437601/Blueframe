from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Protocol
from uuid import uuid4


class CredentialStore(Protocol):
    def put(self, name: str, secret: str) -> str: ...
    def get(self, reference: str) -> str | None: ...
    def delete(self, reference: str) -> None: ...


class WindowsCredentialApi(Protocol):
    def write(self, target: str, secret: str) -> None: ...
    def read(self, target: str) -> str | None: ...
    def delete(self, target: str) -> None: ...


class InMemoryCredentialStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def put(self, name: str, secret: str) -> str:
        reference = f"memory:{name}:{uuid4()}"
        self._values[reference] = secret
        return reference

    def get(self, reference: str) -> str | None:
        return self._values.get(reference)

    def delete(self, reference: str) -> None:
        self._values.pop(reference, None)


class WindowsCredentialStore:
    _REFERENCE_PREFIX = "wincred:"
    _TARGET_PREFIX = "BlueFrame/"

    def __init__(self, api: WindowsCredentialApi | None = None) -> None:
        self._api = api or _CtypesWindowsCredentialApi()

    def put(self, name: str, secret: str) -> str:
        if not name or not secret:
            raise ValueError("credential name and secret are required")
        target = f"{self._TARGET_PREFIX}{name}"
        self._api.write(target, secret)
        return f"{self._REFERENCE_PREFIX}{target}"

    def get(self, reference: str) -> str | None:
        return self._api.read(self._target(reference))

    def delete(self, reference: str) -> None:
        self._api.delete(self._target(reference))

    def _target(self, reference: str) -> str:
        if not reference.startswith(self._REFERENCE_PREFIX):
            raise ValueError("invalid credential reference")
        target = reference.removeprefix(self._REFERENCE_PREFIX)
        if not target.startswith(self._TARGET_PREFIX):
            raise ValueError("invalid credential reference")
        return target


class _CredentialW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


class _CtypesWindowsCredentialApi:
    _CRED_TYPE_GENERIC = 1
    _CRED_PERSIST_LOCAL_MACHINE = 2
    _ERROR_NOT_FOUND = 1168

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Windows Credential Manager is unavailable")
        self._api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        self._api.CredWriteW.argtypes = [ctypes.POINTER(_CredentialW), wintypes.DWORD]
        self._api.CredWriteW.restype = wintypes.BOOL
        self._api.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(_CredentialW)),
        ]
        self._api.CredReadW.restype = wintypes.BOOL
        self._api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self._api.CredDeleteW.restype = wintypes.BOOL
        self._api.CredFree.argtypes = [ctypes.c_void_p]

    def write(self, target: str, secret: str) -> None:
        blob = secret.encode("utf-16-le")
        buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        credential = _CredentialW(
            Type=self._CRED_TYPE_GENERIC,
            TargetName=target,
            CredentialBlobSize=len(blob),
            CredentialBlob=buffer,
            Persist=self._CRED_PERSIST_LOCAL_MACHINE,
            UserName="BlueFrame Studio",
        )
        if not self._api.CredWriteW(ctypes.byref(credential), 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def read(self, target: str) -> str | None:
        pointer = ctypes.POINTER(_CredentialW)()
        if not self._api.CredReadW(target, self._CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            error = ctypes.get_last_error()
            if error == self._ERROR_NOT_FOUND:
                return None
            raise ctypes.WinError(error)
        try:
            credential = pointer.contents
            blob = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            return blob.decode("utf-16-le")
        finally:
            self._api.CredFree(pointer)

    def delete(self, target: str) -> None:
        if self._api.CredDeleteW(target, self._CRED_TYPE_GENERIC, 0):
            return
        error = ctypes.get_last_error()
        if error != self._ERROR_NOT_FOUND:
            raise ctypes.WinError(error)
