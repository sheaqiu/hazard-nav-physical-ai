from glob import glob
import os

from setuptools import find_packages, setup


package_name = "hazard_nav"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "worlds"), glob("worlds/*")),
        (os.path.join("share", package_name, "missions"), glob("missions/*.json")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Physical AI Student",
    maintainer_email="student@example.invalid",
    description="Voice and LLM guided hazardous-area navigation robot",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "language_planner = hazard_nav.language_planner_node:main",
            "mission_executor = hazard_nav.mission_executor_node:main",
            "mission_file = hazard_nav.mission_file_node:main",
            "operator_console = hazard_nav.operator_console_node:main",
            "voice_operator = hazard_nav.voice_operator_node:main",
        ],
    },
)

