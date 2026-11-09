"""Run the production retained-chest ledger without loading a Minecraft world."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

project = Path(__file__).resolve().parents[4]
source = project / 'mods/MedievalStructures/MedievalStructures/src/main/java/fr/renblood/medievalstructures/manager/RetainedChestRegistry.java'
java_home = os.environ.get('JAVA_HOME')
javac = str(Path(java_home) / 'bin/javac.exe') if java_home else shutil.which('javac')
java = str(Path(java_home) / 'bin/java.exe') if java_home else shutil.which('java')
if not javac or not java:
    raise RuntimeError('Configure JAVA_HOME avec un JDK 17.')

with tempfile.TemporaryDirectory(prefix='renblood-retained-') as directory:
    subprocess.run([javac, '-encoding', 'UTF-8', '-d', directory, str(source), str(Path(__file__).with_name('RetainedChestChecks.java'))], check=True)
    subprocess.run([java, '-cp', directory, 'RetainedChestChecks'], check=True)
