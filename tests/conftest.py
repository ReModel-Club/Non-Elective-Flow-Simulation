# conftest.py is a special file that pytest loads automatically before running
# any tests in this folder. It is the usual place for shared setup.
#
# Here we only need one bit of setup: add this "tests" folder to Python's
# import search path (sys.path). That lets test files write
# `import regression_scenarios` even when pytest is launched from the project
# root rather than from inside tests/.
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
