#!/usr/bin/env python3
"""
Celery Worker Entry Point
يمكن استخدام هذا الملف لتشغيل Celery Worker منفصلاً
"""

from app import celery

if __name__ == '__main__':
    celery.start()
