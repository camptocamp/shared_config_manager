from setuptools import find_packages, setup


def long_description():
    try:
        with open("README.md", encoding="utf-8") as readme:
            return readme.read()
    except FileNotFoundError:
        return ""


setup(
    name="shared_config_manager",
    version="1.0",
    description="Shared Config Manager",
    long_description=long_description(),
    classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
    ],
    author="Camptocamp",
    author_email="info@camptocamp.com",
    url="",
    keywords="web pyramid pylons",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[],
    tests_require=[],
    entry_points={
        "console_scripts": ["shared-config-slave = shared_config_manager.scripts.shared_config_slave:main"],
        "paste.app_factory": ["main = shared_config_manager:main"],
    },
    scripts=["scripts/scm-is-ready", "scripts/git-sparse-clone"],
)
