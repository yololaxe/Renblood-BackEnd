"""Regression checks for camp chest positions and exploration area separation."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

project = Path(__file__).resolve().parents[4]
source = project / 'mods/MedievalStructures/MedievalStructures/src/main/java/fr/renblood/medievalstructures/manager/CampLayout.java'
java_home = os.environ.get('JAVA_HOME')
javac = str(Path(java_home) / 'bin/javac.exe') if java_home else shutil.which('javac')
java = str(Path(java_home) / 'bin/java.exe') if java_home else shutil.which('java')
if not javac or not java:
    raise RuntimeError('Configure JAVA_HOME avec un JDK 17 pour vérifier les positions des camps.')

with tempfile.TemporaryDirectory(prefix='renblood-layout-') as directory:
    subprocess.run([javac, '-d', directory, str(source), str(Path(__file__).with_name('CampLayoutChecks.java'))], check=True)
    subprocess.run([java, '-cp', directory, 'CampLayoutChecks'], check=True)
