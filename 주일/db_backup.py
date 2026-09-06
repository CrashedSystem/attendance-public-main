# -*- coding: utf-8 -*-
"""군종.db 백업 모듈.

- 서버 시작 시 자동 백업 (하루 1회) + EXE 실행 시 실행 직전 백업
- 백업 파일: backups/군종_YYYYMMDD_HHMMSS.db.bak  (.bak 형식)
- 보관 개수 초과 시 오래된 것부터 삭제 (기본 30개)
- CLI 수동 실행: python db_backup.py [보관개수]
"""
import glob
import os
import shutil
import sys
import time

from config import BASE_DIR, DB_PATH

BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
DEFAULT_KEEP = 30


def do_backup(keep=DEFAULT_KEEP):
    """지금 시각으로 백업 파일 하나 생성 후 정리. 생성 경로 반환."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(BACKUP_DIR, '군종_%s.db.bak' % stamp)
    shutil.copy2(DB_PATH, dst)
    prune(keep)
    return dst


def prune(keep=DEFAULT_KEEP):
    """오래된 백업 정리. 최신 keep개만 남긴다."""
    files = sorted(glob.glob(os.path.join(BACKUP_DIR, '군종_*.db.bak')))
    for f in files[:-keep] if len(files) > keep else []:
        try:
            os.remove(f)
        except OSError:
            pass


def daily_backup(keep=DEFAULT_KEEP):
    """같은 날 백업이 이미 있으면 생략하고 None, 아니면 do_backup() 결과 반환."""
    today = time.strftime('%Y%m%d')
    if glob.glob(os.path.join(BACKUP_DIR, '군종_%s_*.db.bak' % today)):
        return None
    return do_backup(keep)


if __name__ == '__main__':
    keep = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_KEEP
    path = do_backup(keep)
    print('백업 완료: %s' % path)
    print('백업 폴더: %s' % BACKUP_DIR)