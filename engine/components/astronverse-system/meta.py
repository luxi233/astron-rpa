from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.config import config
from astronverse.baseline.config.config import load_config
from astronverse.system.assert_core import Assert
from astronverse.system.clipboard import Clipboard
from astronverse.system.compress import Compress
from astronverse.system.device import Device
from astronverse.system.file import File
from astronverse.system.folder import Folder
from astronverse.system.printer import Printer
from astronverse.system.process import Process
from astronverse.system.screen import Screen
from astronverse.system.system import System


def get_version():
    pyproject_data = load_config("pyproject.toml")
    return pyproject_data["project"]["version"]


if __name__ == "__main__":
    config.set_config_file("config.yaml")
    atomicMg.register(Assert, group_key="Assert", version=get_version())
    atomicMg.register(Clipboard, group_key="System", version=get_version())
    atomicMg.register(Compress, group_key="System", version=get_version())
    atomicMg.register(Device, group_key="Device", version=get_version())
    atomicMg.register(File, group_key="File", version=get_version())
    atomicMg.register(Folder, group_key="Folder", version=get_version())
    atomicMg.register(Printer, group_key="Printer", version=get_version())
    atomicMg.register(Process, group_key="System", version=get_version())
    atomicMg.register(Screen, group_key="Screen", version=get_version())
    atomicMg.register(System, group_key="System", version=get_version())
    atomicMg.meta()
