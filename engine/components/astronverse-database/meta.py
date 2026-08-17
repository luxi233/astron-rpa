from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.config import config
from astronverse.baseline.config.config import load_config
from astronverse.database.database import Database
from astronverse.database.postgresql import Postgres
from astronverse.database.sqlite import Sqlite


def get_version():
    pyproject_data = load_config("pyproject.toml")
    return pyproject_data["project"]["version"]


if __name__ == "__main__":
    config.set_config_file("config.yaml")
    atomicMg.register(Database, version=get_version())
    atomicMg.register(Sqlite, version=get_version())
    atomicMg.register(Postgres, version=get_version())
    atomicMg.meta()
