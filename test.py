import os
import time

os.chdir(os.getcwd())

path = 'Cache/testphp.vulnweb.com/logo.gif'

modification_time = os.path.getmtime(path)
print("Last modification time since the epoch:", modification_time)