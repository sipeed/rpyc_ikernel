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
    version="0.2.1",
    description="Running IPython kernels through batch queues",
    author="Juwan",
    author_email="junhuanchen@qq.com",
    license="BSD",
    url="https://github.com/junhuanchen/rpyc_ikernel",
    packages=["rpyc_ikernel"],
    scripts=scripts,
    # entry_points={"console_scripts": ["rpyc_ikernel = rpyc_ikernel.__main__:main"]},
    install_requires=["notebook", "pexpect", "rpyc"],
    tests_requires=["pytest", "scripttest"],
    classifiers=[
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Framework :: IPython",
        "License :: OSI Approved :: BSD License",
    ],
)
