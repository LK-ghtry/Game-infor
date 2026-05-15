import subprocess, sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

WORK_DIR = r'E:\CC\game agent'
PYTHON = r'C:\Python314\python.exe'

os.chdir(WORK_DIR)

subprocess.run(['git', 'pull', 'origin', 'main'], cwd=WORK_DIR)

r1 = subprocess.run([PYTHON, '-u', 'monitor.py'], cwd=WORK_DIR)
print(f'monitor exit: {r1.returncode}')

r2 = subprocess.run([PYTHON, '-u', 'daily_report.py'], cwd=WORK_DIR)
print(f'report exit: {r2.returncode}')

sys.exit(0 if r1.returncode == 0 and r2.returncode == 0 else 1)
