from setuptools import setup, find_packages

requires = []

def long_description():
    try:
        return open('README.md').read()
    except FileNotFoundError:
        return ""

setup(name='shared_config_manager',
      version='0.0',
      description='Shared Config Manager',
      long_description=long_description(),
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='Camptocamp',
      author_email='info@camptocamp.com',
      url='',
      keywords='web pyramid pylons',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=requires,
      entry_points="""\
      [paste.app_factory]
      main = shared_config_manager:main
      """,
)
