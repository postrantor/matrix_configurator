# IMPORTANT, you must do this before importing openpyxl
from unittest import mock
# Set max font family value to 99
p = mock.patch('openpyxl.styles.fonts.Font.family.max', new=99)
p.start()

import openpyxl
