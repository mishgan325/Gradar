#!/usr/bin/env python
import os
import sys
import pytest

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gradar.test_settings')
    sys.exit(pytest.main(sys.argv[1:]))

if __name__ == '__main__':
    main() 