# default to setuptools so that 'setup.py develop' is available,
# but fall back to standard modules that do the same
try:
    from setuptools import setup

    scripts = []
except ImportError:
    from distutils.core import setup

    scripts = ["bin/rpyc_ikernel"]

setup(
    name="rpyc_ikernel",
    version="0.3.8",
    description="rpyc for jupyter kernel",
    long_description=open('readme.md', 'r', encoding='UTF-8').read(),
    long_description_content_type='text/markdown',
    author="Juwan",
    author_email="juwan@sipeed.com",
    license="BSD",
    url="https://github.com/sipeed/rpyc_ikernel",
    packages=["rpyc_ikernel"],
    # scripts=scripts,
    # entry_points={"console_scripts": ["rpyc_ikernel = rpyc_ikernel.__main__:main"]},
    install_requires=["notebook", "pexpect", "rpyc", "pillow", "requests"],
    tests_requires=["pytest", "scripttest"],
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Framework :: IPython",
        "License :: OSI Approved :: BSD License",
    ],
)
