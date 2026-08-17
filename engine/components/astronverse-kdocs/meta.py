from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.config import config
from astronverse.actionlib.types import typesMg
from astronverse.baseline.config.config import load_config
from astronverse.kdocs.core_kdocs import WpsHookClient
from astronverse.kdocs.kdocs import Kdocs


def get_version():
    pyproject_data = load_config("pyproject.toml")
    return pyproject_data["project"]["version"]


if __name__ == "__main__":
    config.set_config_file("config.yaml")
    atomicMg.register(Kdocs, group_key="WPS", version=get_version())
    atomicMg.meta()

    config.set_config_file("config_type.yaml")
    typesMg.register_types(WpsHookClient, version=get_version(), channel="global", template="WPS连接对象")
    typesMg.meta()
