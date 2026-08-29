# -*- coding: utf-8 -*-
"""시간 동기화 비즈니스 로직 (NTP 조회 + 시스템 시간 설정)."""
import os
import socket
import struct
import datetime

from constants import NTP_HOSTS, NTP_TIMEOUT


def _ntp_time(host=None, timeout=NTP_TIMEOUT):
    """NTP 서버에서 현재 UTC 시간(epoch 초)을 얻는다.

    단일 서버가 불안정/차단될 수 있으므로 여러 서버를 순서대로 시도한다.
    """
    if host:
        hosts = [host]
    else:
        hosts = NTP_HOSTS
    data = b'\x1b' + 47 * b'\0'
    last_err = None
    for h in hosts:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        try:
            s.sendto(data, (h, 123))
            resp, _ = s.recvfrom(1024)
            t = struct.unpack('!12I', resp)[10]
            return t - 2208988800
        except Exception as e:
            last_err = e
        finally:
            s.close()
    raise last_err or RuntimeError('NTP 서버에 연결할 수 없습니다.')


def _enable_systemtime_privilege():
    """현재 프로세스 토큰에서 SE_SYSTEMTIME_NAME 권한을 활성화한다. 성공 시 True."""
    import ctypes
    from ctypes import wintypes

    SE_SYSTEMTIME_NAME = 'SeSystemtimePrivilege'
    SE_PRIVILEGE_ENABLED = 0x00000002
    TOKEN_ADJUST_PRIVILEGES = 0x0020
    TOKEN_QUERY = 0x0008

    class LUID(ctypes.Structure):
        _fields_ = [('LowPart', wintypes.DWORD), ('HighPart', ctypes.c_long)]

    class LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [('Luid', LUID), ('Attributes', wintypes.DWORD)]

    class TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [('PrivilegeCount', wintypes.DWORD),
                    ('Privileges', LUID_AND_ATTRIBUTES)]

    advapi = ctypes.windll.advapi32
    kernel = ctypes.windll.kernel32

    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(),
                                   TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
                                   ctypes.byref(token)):
        return False
    try:
        luid = LUID()
        if not advapi.LookupPrivilegeValueW(None, SE_SYSTEMTIME_NAME, ctypes.byref(luid)):
            return False
        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
        return bool(advapi.AdjustTokenPrivileges(token, False, ctypes.byref(tp), 0, None, None))
    finally:
        kernel.CloseHandle(token)


def _set_system_time(dt):
    """시스템 시간(UTC)을 설정한다. 플랫폼별로 처리. 성공 시 True 반환."""
    if os.name == 'posix':
        return _set_system_time_linux(dt)
    return _set_system_time_windows(dt)


def _set_system_time_windows(dt):
    """Windows 시스템 시간(UTC)을 설정한다. 관리자 권한 필요. 성공 시 True 반환."""
    import ctypes
    from ctypes import wintypes
    _enable_systemtime_privilege()

    class SYSTEMTIME(ctypes.Structure):
        _fields_ = [('wYear', wintypes.WORD), ('wMonth', wintypes.WORD),
                    ('wDayOfWeek', wintypes.WORD), ('wDay', wintypes.WORD),
                    ('wHour', wintypes.WORD), ('wMinute', wintypes.WORD),
                    ('wSecond', wintypes.WORD), ('wMilliseconds', wintypes.WORD)]

    st = SYSTEMTIME()
    st.wYear = dt.year
    st.wMonth = dt.month
    st.wDay = dt.day
    st.wHour = dt.hour
    st.wMinute = dt.minute
    st.wSecond = dt.second
    st.wMilliseconds = dt.microsecond // 1000
    return bool(ctypes.windll.kernel32.SetSystemTime(ctypes.byref(st)))


def _set_system_time_linux(dt):
    """Linux(systemd)에서 시스템 시간을 설정한다. root 필요. 성공 시 True 반환.

    timedatectl set-time은 로컬 시간 문자열을 받으므로, UTC로 주어진 dt를 로컬 시간대로 변환한다.
    """
    import subprocess
    aware = dt.replace(tzinfo=datetime.timezone.utc)
    local = aware.astimezone()
    iso = local.strftime('%Y-%m-%d %H:%M:%S')
    try:
        subprocess.run(['timedatectl', 'set-time', iso], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        return True
    except Exception:
        return False


def get_time_info():
    """현재 시스템(로컬) 시간과 인터넷(NTP) 시간을 표시한다. (읽기 전용)"""
    internet = None
    try:
        internet = datetime.datetime.utcfromtimestamp(_ntp_time())
    except Exception:
        internet = None
    return {
        'system_local': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'system_utc': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'internet_utc': internet.strftime('%Y-%m-%d %H:%M:%S') if internet else None,
    }


def sync_time():
    """인터넷(NTP) 시간으로 컴퓨터 시스템 시간을 동기화한다.

    반환: (응답 dict, HTTP 상태 코드)
    """
    try:
        epoch = _ntp_time()
        dt = datetime.datetime.utcfromtimestamp(epoch)
    except Exception as e:
        return ({'ok': False, 'msg': '인터넷 시간을 가져오지 못했습니다. 네트워크를 확인하세요. (%s)' % e}, 500)
    try:
        ok = _set_system_time(dt)
    except Exception as e:
        return ({'ok': False, 'msg': '시스템 시간 설정 실패. 관리자 권한으로 실행해야 합니다. (%s)' % e}, 500)
    if not ok:
        return ({'ok': False, 'msg': '시스템 시간 설정 실패. 관리자 권한으로 실행해야 합니다.'}, 500)
    return ({
        'ok': True,
        'set_utc': dt.strftime('%Y-%m-%d %H:%M:%S'),
        'local_now': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }, 200)
