"""
rpyc ikernel entry point.

From here you can get to 'manage', otherwise it is assumed
that a kernel is required instead and instance one instead.
"""

from ipykernel.kernelapp import IPKernelApp
from .kernel import RPycKernel

IPKernelApp.launch_instance(kernel_class=RPycKernel)
